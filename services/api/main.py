import logging
import os
import shutil
import threading
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional, TypedDict

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from services.api.app.config.settings import settings
from services.api.app.observability.metrics import metrics_service
from services.api.app.observability.tracing import Trace, span, start_trace
from services.api.app.orchestrator import nodes
from services.api.app.orchestrator.graph import legal_graph
from services.api.app.orchestrator.state import AnalysisResult
from services.api.app.services.documents import document_registry
from services.api.app.services.inference import inference_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
logger = logging.getLogger("zeroday.api")

UPLOAD_DIR = settings.UPLOAD_DIR
os.makedirs(UPLOAD_DIR, exist_ok=True)

ANALYSIS_SECTIONS = (
    ("answer_analysis", "Answer"),
)

_startup = {"warmup": None}


def _warmup():
    try:
        _startup["warmup"] = inference_client.warmup()
        logger.info("model warm-up done %s", _startup["warmup"])
    except Exception as e:
        _startup["warmup"] = {"error": type(e).__name__}
        logger.warning("model warm-up failed: %s", type(e).__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.WARMUP_ON_STARTUP and hasattr(inference_client, "warmup"):
        threading.Thread(target=_warmup, daemon=True).start()
    yield


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

# Privacy: Strict CORS for local-only operation
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Server-Timing", "X-Request-ID", "X-Response-Time-Ms"],
)


@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    request.state.request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.1f}"
    return response


class AnalysisSection(TypedDict):
    title: str
    content: str
    evidence: list
    verified: bool


def build_analysis_sections(result: dict) -> list:
    sections = []
    for key, title in ANALYSIS_SECTIONS:
        analysis = result.get(key)
        if not isinstance(analysis, AnalysisResult) or not analysis.findings:
            continue

        verified = not analysis.findings[0].startswith("Verification failed:")
        sections.append({
            "title": title,
            "content": (
                analysis.findings[0]
                if verified
                else "I couldn't confirm a clear answer from the document text."
            ),
            "evidence": analysis.evidence if verified else [],
            "verified": verified,
        })
    return sections


def _traced_json(trace: Trace, body: dict, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        {**body, "request_id": trace.request_id, "timings": trace.summary()},
        status_code=status_code,
        headers={"Server-Timing": trace.server_timing_header()},
    )


def _find_document(doc_id: str) -> Optional[str]:
    for ext in settings.ALLOWED_EXTENSIONS:
        path = os.path.join(UPLOAD_DIR, f"{doc_id}{ext}")
        if os.path.exists(path):
            return path
    return None


@app.get("/health")
def health_check():
    return {"status": "healthy", "model": settings.OLLAMA_MODEL}


@app.get("/health/ready")
def readiness():
    """Local runtime reachability, model residency and warm-up cost."""
    return {"model": settings.OLLAMA_MODEL, "ollama": inference_client.status(), "warmup": _startup["warmup"]}


@app.get("/dashboard/metrics")
def get_metrics(window_s: Optional[float] = None):
    return metrics_service.get_aggregate_metrics(window_s)


@app.get("/dashboard/latency")
def get_latency(window_s: Optional[float] = None):
    return metrics_service.get_stage_latency(window_s)


@app.get("/dashboard/logs")
def get_logs(limit: int = 50):
    return metrics_service.get_recent_logs(limit)


@app.get("/dashboard/trace/{request_id}")
def get_trace(request_id: str):
    return metrics_service.get_trace_for_request(request_id)


# Endpoints are sync so FastAPI runs them in a worker thread: a slow model call
# no longer blocks the event loop (health checks and dashboards stay responsive).
@app.post("/upload")
def upload_document(request: Request, file: UploadFile = File(...)):
    with start_trace("/upload", request.state.request_id) as trace:
        ext = os.path.splitext(file.filename or "")[1].lower()
        if ext not in settings.ALLOWED_EXTENSIONS:
            return _traced_json(trace, {"error": "Only PDF and TXT files are supported."}, 400)

        doc_id = str(uuid.uuid4())
        file_path = os.path.join(UPLOAD_DIR, f"{doc_id}{ext}")
        with span("upload.save") as s:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            size = os.path.getsize(file_path)
            s.attrs["bytes"] = size
        if size > settings.MAX_UPLOAD_MB * 1024 * 1024:
            os.remove(file_path)
            return _traced_json(trace, {"error": f"File is larger than {settings.MAX_UPLOAD_MB} MB."}, 413)

        # Parse, index and classify now so the first question only pays for the answer.
        category, status = None, "ok"
        try:
            with span("request.upload"):
                record = document_registry.load(file_path)
                if not record.text:
                    raise ValueError("empty")
                try:
                    category, _ = nodes.classify_document(record.doc_key, record.text)
                except Exception as e:
                    status = "degraded"
                    logger.warning("classification deferred: %s", type(e).__name__)
        except Exception as e:
            os.remove(file_path)
            metrics_service.record_trace(trace, doc_id, False, "extract_failed", status="error")
            logger.warning("upload failed: %s", type(e).__name__)
            return _traced_json(
                trace,
                {"error": "I couldn't read any text from that file. It may be scanned, encrypted or damaged."},
                400,
            )

        metrics_service.record_trace(trace, doc_id, category not in (None, "non_legal"), category or "pending", status=status)
        return _traced_json(trace, {"doc_id": doc_id, "filename": file.filename, "category": category})


@app.post("/chat")
def chat(request: Request, doc_id: str = Form(...), query: str = Form(...)):
    with start_trace("/chat", request.state.request_id) as trace:
        found_path = _find_document(doc_id)
        if not found_path:
            return _traced_json(trace, {"error": "Document not found. Please upload it again."}, 404)

        inputs = {"doc_id": found_path, "user_query": query, "is_legal_doc": False}
        try:
            with span("request.chat", query_chars=len(query)):
                final_state = legal_graph.invoke(inputs)
        except Exception as e:
            metrics_service.record_trace(trace, doc_id, False, "error", status="error")
            logger.warning("chat failed: %s", type(e).__name__)
            return _traced_json(
                trace,
                {"error": "The local model isn't responding. Check that Ollama is running, then try again."},
                503,
            )

        if final_state.get("policy_refusal"):
            metrics_service.record_trace(trace, doc_id, True, "escalated")
            return _traced_json(trace, {"response": final_state["final_response"], "sections": []})

        if not final_state.get("is_legal_doc"):
            metrics_service.record_trace(trace, doc_id, False, "non_legal")
            return _traced_json(trace, {
                "response": (
                    "This file doesn't appear to contain a legal document, so I couldn't analyze it. "
                    "Try uploading a contract, lease, employment agreement, or legal notice."
                )
            })

        if final_state.get("document_silent"):
            metrics_service.record_trace(trace, doc_id, True, "silent")
            return _traced_json(trace, {"response": final_state["final_response"], "sections": []})

        response = final_state.get("final_response") or "No analysis could be generated."
        if response.startswith("Safety Error:"):
            outcome = "blocked"
            response = "I couldn't safely summarize this document. Please consult a qualified legal professional."
            sections = []
        else:
            sections = build_analysis_sections(final_state)
            outcome = "analyzed" if sections and sections[0]["verified"] else "ungrounded"

        metrics_service.record_trace(trace, doc_id, True, outcome)
        return _traced_json(trace, {"response": response, "sections": sections})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.BIND_ADDRESS, port=settings.BIND_PORT)
