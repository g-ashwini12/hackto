import json
import os
import sqlite3
import tempfile
import unittest

from fastapi.testclient import TestClient

import services.api.app.orchestrator.nodes as nodes_module
import services.api.main as main_module
from services.api.app.observability.metrics import MetricsService, percentile
from services.api.app.observability.tracing import span, start_trace
from services.api.app.orchestrator.graph import legal_graph
from services.api.app.orchestrator.policy import safety_service
from services.api.app.services.inference import MockInferenceClient
from services.api.app.services.retrieval import BM25Index

SECRET = "Zebulon Quartermaine"
DOC = (
    f"This rental agreement is between {SECRET} and the Tenant. "
    "The Tenant shall pay rent of Rs. 15,000 on the 5th day of each month. "
    "Either party may terminate this agreement by giving two months written notice."
)


class CountingClient(MockInferenceClient):
    def __init__(self, answer="The Tenant shall pay rent of Rs. 15,000 on the 5th day of each month."):
        self.prompts = []
        self.answer = answer

    def generate(self, prompt, system=None):
        self.prompts.append(prompt)
        if "category" in prompt.lower():
            return super().generate(prompt, system)
        return self.answer


class TestTracing(unittest.TestCase):
    def setUp(self):
        self.client = CountingClient()
        nodes_module.inference_client = self.client
        self.tmp = tempfile.mkdtemp()
        self.doc = os.path.join(self.tmp, "lease.txt")
        with open(self.doc, "w") as f:
            f.write(f"{DOC} Reference {self.id()}.")

    def test_node_and_stage_spans_are_recorded(self):
        with start_trace("/chat") as trace:
            legal_graph.invoke({"doc_id": self.doc, "user_query": "When is rent due?", "is_legal_doc": False})
        names = [s.name for s in trace.spans]
        for expected in ("node.policy_gate", "node.ingestion", "ingest.extract", "route.keywords",
                         "retrieval.query", "llm.answer", "verify.grounding", "policy.output"):
            self.assertIn(expected, names)
        self.assertTrue(all(s.duration_ms >= 0 for s in trace.spans))
        self.assertIn("llm_answer;dur=", trace.server_timing_header())

    def test_second_question_reuses_parse_index_and_classification(self):
        legal_graph.invoke({"doc_id": self.doc, "user_query": "When is rent due?", "is_legal_doc": False})
        self.assertEqual(len(self.client.prompts), 1, "clear rental keywords skip the classify call")
        with start_trace("/chat") as trace:
            legal_graph.invoke({"doc_id": self.doc, "user_query": "How do I terminate?", "is_legal_doc": False})
        names = [s.name for s in trace.spans]
        self.assertEqual(len(self.client.prompts), 2, "only the answer call should run again")
        self.assertIn("ingest.cache", names)
        self.assertIn("route.cache", names)
        self.assertNotIn("ingest.extract", names)

    def test_verdict_question_is_escalated_without_model_call(self):
        result = legal_graph.invoke({"doc_id": self.doc, "user_query": "Is this clause enforceable?", "is_legal_doc": False})
        self.assertTrue(result["policy_refusal"])
        self.assertIn("qualified lawyer", result["final_response"])
        self.assertEqual(self.client.prompts, [])

    def test_span_attrs_drop_free_text(self):
        with start_trace("/chat") as trace:
            with span("x", note=SECRET, chars=10, model="gemma3:1b"):
                pass
        self.assertEqual(trace.spans[0].attrs, {"chars": 10, "model": "gemma3:1b"})


class TestPolicy(unittest.TestCase):
    def test_verdict_questions(self):
        for q in ["Is this enforceable?", "Is this agreement legal?", "Should I sign this?",
                  "Will I win if I sue?", "Is the lock-in clause legally binding?"]:
            self.assertTrue(safety_service.check_question(q)[0], q)
        for q in ["When is rent due?", "What does the termination clause say?", "Is this okay?"]:
            self.assertFalse(safety_service.check_question(q)[0], q)


class TestMetrics(unittest.TestCase):
    def test_percentile(self):
        self.assertEqual(percentile([10, 20, 30, 40, 50], 50), 30)
        self.assertEqual(percentile([], 95), None)

    def test_stage_latency_and_trace_waterfall(self):
        db = os.path.join(tempfile.mkdtemp(), "m.db")
        svc = MetricsService(db)
        with start_trace("/chat") as trace:
            with span("llm.answer", tokens_per_s=20.0, prompt_tokens=100, completion_tokens=30):
                pass
            with span("retrieval.query"):
                pass
        svc.record_trace(trace, "doc", True, "analyzed")
        stages = svc.get_stage_latency()
        self.assertEqual(stages["llm.answer"]["count"], 1)
        self.assertIn("p95_ms", stages["retrieval.query"])
        agg = svc.get_aggregate_metrics()
        self.assertEqual(agg["total_requests"], 1)
        self.assertEqual(agg["total_tokens"], 130)
        self.assertEqual(agg["avg_tokens_per_s"], 20.0)
        self.assertEqual([s["name"] for s in svc.get_trace_for_request(trace.request_id)], ["llm.answer", "retrieval.query"])


class TestBM25(unittest.TestCase):
    def test_ranks_relevant_chunk_first(self):
        idx = BM25Index(["The tenant pays rent monthly.", "Termination requires two months notice.", "Pets are not allowed."])
        self.assertEqual(idx.search("how do I terminate with notice", 1)[0][0], 1)


class TestApi(unittest.TestCase):
    def setUp(self):
        self.client_llm = CountingClient()
        nodes_module.inference_client = self.client_llm
        self.http = TestClient(main_module.app)

    def test_upload_then_chat_exposes_timings_and_keeps_content_out_of_metrics(self):
        up = self.http.post("/upload", files={"file": ("lease.txt", DOC.replace("5th", "7th").encode(), "text/plain")})
        self.assertEqual(up.status_code, 200, up.text)
        self.assertEqual(up.json()["category"], "rental")
        self.assertIn("Server-Timing", up.headers)

        res = self.http.post("/chat", data={"doc_id": up.json()["doc_id"], "query": "When is rent due?"})
        body = res.json()
        self.assertEqual(res.status_code, 200, res.text)
        self.assertIn("llm_answer;dur=", res.headers["Server-Timing"])
        self.assertIn("X-Response-Time-Ms", res.headers)
        self.assertIn("llm.answer", body["timings"]["stages_ms"])
        self.assertNotIn("llm.classify", body["timings"]["stages_ms"], "classification happens at upload")

        trace = self.http.get(f"/dashboard/trace/{body['request_id']}").json()
        self.assertIn("llm.answer", [s["name"] for s in trace])
        self.assertIn("llm.answer", self.http.get("/dashboard/latency").json())

        with sqlite3.connect(main_module.metrics_service.db_path) as conn:
            dump = json.dumps([list(r) for t in ("request_metrics", "spans") for r in conn.execute(f"SELECT * FROM {t}")])
        self.assertNotIn(SECRET, dump)
        self.assertNotIn("When is rent due", dump)

    def test_bad_inputs_return_http_errors(self):
        self.assertEqual(self.http.post("/upload", files={"file": ("x.exe", b"MZ", "application/octet-stream")}).status_code, 400)
        self.assertEqual(self.http.post("/upload", files={"file": ("x.pdf", b"not a pdf", "application/pdf")}).status_code, 400)
        self.assertEqual(self.http.post("/chat", data={"doc_id": "missing", "query": "hi"}).status_code, 404)


if __name__ == "__main__":
    unittest.main()


class TestDocumentSilence(unittest.TestCase):
    def setUp(self):
        self.client = CountingClient()
        nodes_module.inference_client = self.client
        self.tmp = tempfile.mkdtemp()
        self.doc = os.path.join(self.tmp, "lease.txt")
        with open(self.doc, "w") as f:
            f.write(f"{DOC} Reference {self.id()}.")

    def _ask(self, q):
        with start_trace("/chat") as trace:
            state = legal_graph.invoke({"doc_id": self.doc, "user_query": q, "is_legal_doc": False})
        return state, trace

    def test_unmentioned_topic_is_silent_without_answer_call(self):
        self._ask("When is rent due?")
        calls = len(self.client.prompts)
        state, trace = self._ask("Does the agreement mention pets?")
        self.assertTrue(state.get("document_silent"))
        self.assertIn("\u201cpets\u201d", state["final_response"])
        self.assertEqual(len(self.client.prompts), calls)
        self.assertNotIn("llm.answer", [s.name for s in trace.spans])

    def test_word_variants_are_not_treated_as_silent(self):
        state, _ = self._ask("How can it be terminated?")
        self.assertFalse(state.get("document_silent"))
        self.assertIn("final_response", state)

    def test_silent_outcome_over_api(self):
        api = TestClient(main_module.app)
        with open(self.doc, "rb") as f:
            doc_id = api.post("/upload", files={"file": ("lease.txt", f, "text/plain")}).json()["doc_id"]
        r = api.post("/chat", data={"doc_id": doc_id, "query": "Is smoking allowed?"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("silent", r.json()["response"])
        logs = api.get("/dashboard/logs").json()
        self.assertIn("silent", json.dumps(logs))


class TestKeywordCategory(unittest.TestCase):
    def test_clear_documents_skip_the_model(self):
        self.assertEqual(nodes_module.keyword_category(DOC), "rental")
        self.assertEqual(
            nodes_module.keyword_category("The Employer offers the Employee a salary after a probation period."),
            "employment",
        )

    def test_ambiguous_documents_fall_back_to_gemma(self):
        self.assertIsNone(nodes_module.keyword_category("This is a rental agreement."))
        self.assertIsNone(nodes_module.keyword_category("I love eating apples."))
