from typing import TypedDict, List, Optional
from pydantic import BaseModel


class AnalysisResult(BaseModel):
    category: str
    findings: List[str]
    evidence: List[str]
    risk_level: str = "low"


class GraphState(TypedDict, total=False):
    """State shared across the LangGraph nodes."""
    doc_id: str
    doc_key: str
    user_query: str
    full_text: str
    chunks: List[str]
    retrieved_context: List[str]

    answer_analysis: Optional[AnalysisResult]

    # Final response
    final_response: Optional[str]
    is_legal_doc: bool
    routing_decision: Optional[str]
    policy_refusal: bool
    document_silent: bool
