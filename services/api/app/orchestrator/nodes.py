from services.api.app.services.ingestion import ingestion_service
from services.api.app.services.chunking import chunking_service
from services.api.app.services.retrieval import retrieval_service
from services.api.app.services.inference import inference_client
from services.api.app.prompts.templates import get_prompt, get_system_prompt
from services.api.app.orchestrator.state import GraphState, AnalysisResult
from services.api.app.services.verification import verification_service
from services.api.app.orchestrator.policy import safety_service
from services.api.app.observability.metrics import metrics_service
from services.api.app.observability.manifest import manifest_service
import time
import uuid

def ingestion_node(state: GraphState):
    """Extracts text and chunks the document."""
    start_time = time.time()
    doc_id = state["doc_id"]
    text = ingestion_service.extract_text(doc_id)
    chunks = chunking_service.chunk_text(text)
    retrieval_service.index_document(doc_id, chunks)

    return {
        "full_text": text,
        "chunks": chunks
    }

def router_node(state: GraphState):
    """Classifies the document and decides if it's a legal document."""
    text_sample = state["full_text"][:2000]
    prompt = get_prompt("classify_label", text=text_sample)
    system = get_system_prompt("classify_label")

    category = inference_client.generate(prompt, system)
    is_legal = category != "non_legal"

    # Log metric
    metrics_service.log_request(str(uuid.uuid4()), state["doc_id"], 0.1, is_legal, category)

    return {
        "is_legal_doc": is_legal,
        "routing_decision": category
    }

def retrieval_node(state: GraphState):
    """Retrieves relevant context based on the user query."""
    context = retrieval_service.retrieve(state["user_query"], doc_id=state["doc_id"])
    return {"retrieved_context": context}

def analysis_node(state: GraphState, analysis_type: str):
    """Generic analysis node to be used in parallel."""
    prompt_key = {
        "clause": "clause_analysis",
        "risk": "risk_detection",
        "obligation": "clause_analysis",
        "deadline": "clause_analysis"
    }.get(analysis_type, "clause_analysis")

    context = "\n\n".join(state["retrieved_context"])
    prompt = get_prompt(prompt_key, clause=context if "clause" in prompt_key else "", text=context)
    system = get_system_prompt(prompt_key)

    # Reproducibility: Create manifest
    manifest_service.create_manifest(str(uuid.uuid4()), prompt, "gemma:e4b", {"temp": 0})

    response = inference_client.generate(prompt, system)

    # Verification Step: Grounding
    is_grounded, evidence = verification_service.verify_claim(response, context)

    result = AnalysisResult(
        category=analysis_type,
        findings=[response] if is_grounded else ["Verification failed: Claim not grounded in text."],
        evidence=evidence,
        risk_level="medium"
    )

    return {f"{analysis_type}_analysis": result}

# Wrappers for parallel execution
def analyze_clause(state: GraphState): return analysis_node(state, "clause")
def analyze_risk(state: GraphState): return analysis_node(state, "risk")
def analyze_obligation(state: GraphState): return analysis_node(state, "obligation")
def analyze_deadline(state: GraphState): return analysis_node(state, "deadline")

def merge_node(state: GraphState):
    """Merges results and applies safety validation."""
    results = [
        state.get("clause_analysis"),
        state.get("risk_analysis"),
        state.get("obligation_analysis"),
        state.get("deadline_analysis")
    ]

    findings = []
    for res in results:
        if res:
            findings.append(f"[{res.category.upper()}] {res.findings[0]}")

    summary = "\n\n".join(findings)

    # Safety Validation - Apply after merge
    is_safe, error = safety_service.validate_response(summary)
    if not is_safe:
        summary = f"Safety Error: {error}. Please consult a legal professional."

    return {"final_response": summary}
