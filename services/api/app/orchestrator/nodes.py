import re
from typing import Optional, Tuple

from services.api.app.config.settings import settings
from services.api.app.observability.manifest import manifest_service
from services.api.app.observability.tracing import add_span_attrs, current_trace, span
from services.api.app.orchestrator.policy import ESCALATION_MESSAGE, safety_service, silent_message
from services.api.app.orchestrator.state import AnalysisResult, GraphState
from services.api.app.prompts.templates import get_prompt, get_system_prompt
from services.api.app.services.documents import document_registry
from services.api.app.services.inference import inference_client
from services.api.app.services.retrieval import retrieval_service
from services.api.app.services.verification import verification_service

CATEGORIES = ("rental", "employment", "legal_notice", "service_agreement", "non_legal")


def _llm(stage: str, prompt: str, system: str, max_tokens: Optional[int] = None) -> str:
    """Runs one model call inside an `llm.<stage>` span with Ollama's timings attached."""
    with span(f"llm.{stage}", model=settings.OLLAMA_MODEL, prompt_chars=len(prompt)) as s:
        client = inference_client
        if hasattr(client, "generate_with_meta"):
            meta = client.generate_with_meta(prompt, system, max_tokens=max_tokens)
            add_span_attrs(s, **{k: v for k, v in meta.items() if k != "response"})
            text = meta["response"]
        else:
            text = client.generate(prompt, system)
        add_span_attrs(s, response_chars=len(text))

    trace = current_trace()
    manifest_service.create_manifest(
        trace.request_id if trace else "untraced",
        prompt,
        settings.OLLAMA_MODEL,
        {"temperature": settings.LLM_TEMPERATURE, "num_predict": max_tokens or settings.LLM_MAX_TOKENS},
        stage=stage,
        timings={k: v for k, v in s.attrs.items() if k.endswith(("_ms", "_tokens", "_per_s"))},
    )
    return text


def normalize_category(raw: str) -> str:
    lowered = raw.strip().lower().replace("-", "_").replace(" ", "_")
    for label in CATEGORIES:
        if label in lowered:
            return label
    return lowered or "unknown"


_CATEGORY_KEYWORDS = {
    "rental": ("rental", "tenant", "landlord", "lease", "tenancy", "rent", "lessee", "lessor"),
    "employment": ("employment", "employee", "employer", "salary", "probation", "designation", "appointment"),
    "service_agreement": ("service provider", "client", "deliverables", "statement of work", "service agreement"),
    "legal_notice": ("legal notice", "hereby notified", "notice is hereby", "under instructions from my client"),
}


def keyword_category(text: str) -> Optional[str]:
    """Clear-cut documents are labelled from keywords; ambiguous ones go to Gemma."""
    lowered = text.lower()
    scores = {
        label: sum(1 for kw in kws if re.search(rf"\b{re.escape(kw)}\b", lowered))
        for label, kws in _CATEGORY_KEYWORDS.items()
    }
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    (best, top), (_, second) = ranked[0], ranked[1]
    return best if top >= 3 and top >= 2 * second else None


def classify_document(doc_key: str, text: str) -> Tuple[str, bool]:
    """Classifies once per document; later questions reuse the cached label."""
    record = document_registry.get(doc_key)
    if record is not None and record.category is not None:
        with span("route.cache", cache="hit", category=record.category):
            category = record.category
    else:
        sample = text[: settings.CLASSIFY_SAMPLE_CHARS]
        with span("route.keywords") as s:
            category = keyword_category(sample)
            add_span_attrs(s, matched=category is not None, category=category or "none")
        if category is None:
            prompt = get_prompt("classify_label", text=sample)
            category = normalize_category(_llm("classify", prompt, get_system_prompt("classify_label"), settings.CLASSIFY_MAX_TOKENS))
        if record is not None:
            record.category = category
    return category, category != "non_legal"


def policy_gate_node(state: GraphState):
    """Refuses verdict-seeking questions before spending any model time."""
    with span("policy.input") as s:
        needs_escalation, reason = safety_service.check_question(state.get("user_query", ""))
        add_span_attrs(s, escalated=needs_escalation)
    if needs_escalation:
        return {"policy_refusal": True, "final_response": ESCALATION_MESSAGE, "routing_decision": reason}
    return {"policy_refusal": False}


def ingestion_node(state: GraphState):
    """Extracts, chunks and indexes the document (cached per document content)."""
    record = document_registry.load(state["doc_id"])
    return {"doc_key": record.doc_key, "full_text": record.text, "chunks": record.chunks}


def router_node(state: GraphState):
    """Classifies the document and decides if it's a legal document."""
    category, is_legal = classify_document(state["doc_key"], state["full_text"])
    trace = current_trace()
    if trace:
        trace.set(category=category)
    return {"is_legal_doc": is_legal, "routing_decision": category}


def retrieval_node(state: GraphState):
    """Retrieves relevant context based on the user query."""
    with span("retrieval.coverage") as s:
        subject, missing = retrieval_service.coverage(state["user_query"], state["doc_key"])
        silent = bool(subject) and len(missing) == len(subject)
        add_span_attrs(s, subject_terms=len(subject), missing_terms=len(missing), silent=silent)
    if silent:
        # Nothing in the document mentions the topic: answer deterministically
        # instead of letting the model guess from unrelated passages.
        return {"retrieved_context": [], "document_silent": True, "final_response": silent_message(missing)}

    with span("retrieval.query", backend=retrieval_service.backend) as s:
        context = retrieval_service.retrieve(state["user_query"], doc_id=state["doc_key"])
        add_span_attrs(s, chunks=len(context), lexical_hits=retrieval_service.last_hits)
    return {"retrieved_context": context}


def analyze_question(state: GraphState):
    """Answers the user's question in one grounded model call."""
    context = "\n\n".join(state["retrieved_context"])
    prompt = get_prompt("question_answer", question=state["user_query"], text=context)
    response = _llm("answer", prompt, get_system_prompt("question_answer"))

    with span("verify.grounding") as s:
        is_grounded, evidence = verification_service.verify_claim(response, context)
        add_span_attrs(s, grounded=is_grounded, evidence=len(evidence))

    result = AnalysisResult(
        category="answer",
        findings=[response] if is_grounded else ["Verification failed: Claim not grounded in text."],
        evidence=evidence,
        risk_level="low"
    )
    return {"answer_analysis": result}


def merge_node(state: GraphState):
    """Merges results and applies safety validation."""
    analysis = state.get("answer_analysis")
    summary = "\n\n".join([analysis.findings[0]] if analysis else [])

    with span("policy.output") as s:
        is_safe, error = safety_service.validate_response(summary)
        add_span_attrs(s, blocked=not is_safe)
    if not is_safe:
        summary = f"Safety Error: {error}. Please consult a legal professional."

    return {"final_response": summary}
