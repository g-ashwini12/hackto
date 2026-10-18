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
from services.api.app.config.settings import settings
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

    # Log metric - explicitly cast to ensure SQLite compatibility
    metrics_service.log_request(
        request_id=str(uuid.uuid4()),
        doc_id=str(state["doc_id"]),
        duration=0.1,
        is_legal=bool(is_legal),
        outcome=str(category)
    )

    return {
        "is_legal_doc": is_legal,
        "routing_decision": category
    }

def retrieval_node(state: GraphState):
    """Retrieves relevant context based on the user query."""
    context = retrieval_service.retrieve(state["user_query"], doc_id=state["doc_id"])
    return {"retrieved_context": context}

def analyze_question(state: GraphState):
    """Answers the user's question in one grounded model call."""
    context = "\n\n".join(state["retrieved_context"])
    prompt = get_prompt(
        "question_answer",
        question=state["user_query"],
        text=context,
    )
    system = get_system_prompt("question_answer")

    manifest_service.create_manifest(
        str(uuid.uuid4()),
        prompt,
        settings.OLLAMA_MODEL,
        {"temperature": settings.LLM_TEMPERATURE, "num_predict": settings.LLM_MAX_TOKENS},
    )

    response = inference_client.generate(prompt, system)

    is_grounded, evidence = verification_service.verify_claim(response, context)

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
    findings = [analysis.findings[0]] if analysis else []

    summary = "\n\n".join(findings)

    # Safety Validation - Apply after merge
    is_safe, error = safety_service.validate_response(summary)
    if not is_safe:
        summary = f"Safety Error: {error}. Please consult a legal professional."

    return {"final_response": summary}
