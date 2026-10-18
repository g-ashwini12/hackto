from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from services.api.app.config.settings import settings
from services.api.app.orchestrator.graph import legal_graph
from services.api.app.orchestrator.state import AnalysisResult
from services.api.app.services.ingestion import ingestion_service
from services.api.app.observability.metrics import metrics_service
import shutil
import os
import uuid
import time
from typing import TypedDict

app = FastAPI(title=settings.APP_NAME)

# Privacy: Strict CORS for local-only operation
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ANALYSIS_SECTIONS = (
    ("answer_analysis", "Answer"),
)


class AnalysisSection(TypedDict):
    title: str
    content: str
    evidence: list[str]
    verified: bool


def build_analysis_sections(result: dict[str, object]) -> list[AnalysisSection]:
    sections: list[AnalysisSection] = []
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


@app.get("/health")
async def health_check():
    return {"status": "healthy", "model": settings.OLLAMA_MODEL}

@app.get("/dashboard/metrics")
async def get_metrics():
    return metrics_service.get_aggregate_metrics()

@app.get("/dashboard/logs")
async def get_logs():
    return metrics_service.get_recent_logs()

@app.get("/dashboard/trace/{request_id}")
async def get_trace(request_id: str):
    return metrics_service.get_trace_for_request(request_id)

@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    doc_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{doc_id}{os.path.splitext(file.filename)[1]}")

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Pre-run ingestion to verify it's a legal doc
    try:
        text = ingestion_service.extract_text(file_path)
        # Basic check for non-legal files can be added here
    except Exception as e:
        return {"error": f"Failed to process file: {str(e)}"}, 400

    return {"doc_id": doc_id, "filename": file.filename}

@app.post("/chat")
async def chat(doc_id: str = Form(...), query: str = Form(...)):
    # Path to the uploaded file
    # In a real app, we'd store the path in a DB
    file_exts = ['.pdf', '.txt']
    found_path = None
    for ext in file_exts:
        path = os.path.join(UPLOAD_DIR, f"{doc_id}{ext}")
        if os.path.exists(path):
            found_path = path
            break

    if not found_path:
        return {"error": "Document not found"}, 404

    inputs = {
        "doc_id": found_path,
        "user_query": query,
        "is_legal_doc": False
    }

    request_id = str(uuid.uuid4())
    start_time = time.time()

    # We use a stream to capture node transitions for the observation dashboard
    final_state = {}
    for event in legal_graph.stream(inputs):
        node_name, state_update = next(iter(event.items()))

        # Log the trace for this node transition
        metrics_service.log_trace(
            request_id=request_id,
            node_name=node_name,
            duration=0.0, # Precise per-node timing would require wrapping the node function
            state_snapshot=state_update
        )
        final_state = {**final_state, **state_update}

    duration = time.time() - start_time

    if not final_state.get("is_legal_doc"):
        metrics_service.log_request(request_id, found_path, duration, False, "non_legal")
        return {
            "response": (
                "This file doesn't appear to contain a legal document, so I couldn't analyze it. "
                "Try uploading a contract, lease, employment agreement, or legal notice."
            )
        }

    outcome = "analyzed"
    metrics_service.log_request(request_id, found_path, duration, True, outcome)

    response = final_state.get("final_response") or "No analysis could be generated."
    if response.startswith("Safety Error:"):
        response = "I couldn't safely summarize this document. Please consult a qualified legal professional."
        sections = []
    else:
        sections = build_analysis_sections(final_state)
    return {"response": response, "sections": sections, "request_id": request_id}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.BIND_ADDRESS, port=settings.BIND_PORT)
