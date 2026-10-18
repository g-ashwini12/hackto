from typing import TypedDict, List, Optional, Dict, Any
from pydantic import BaseModel, Field

class AnalysisResult(BaseModel):
    category: str
    findings: List[str]
    evidence: List[str]
    risk_level: str = "low"

class GraphState(TypedDict):
    """State shared across the LangGraph nodes."""
    doc_id: str
    user_query: str
    full_text: str
    chunks: List[str]
    retrieved_context: List[str]

    answer_analysis: Optional[AnalysisResult]

    # Final response
    final_response: Optional[str]
    is_legal_doc: bool
    routing_decision: Optional[str]
