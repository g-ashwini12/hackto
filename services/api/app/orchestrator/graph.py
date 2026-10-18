from langgraph.graph import StateGraph, END

from services.api.app.observability.tracing import traced_node
from services.api.app.orchestrator.state import GraphState
from services.api.app.orchestrator.nodes import (
    policy_gate_node,
    ingestion_node,
    router_node,
    retrieval_node,
    analyze_question,
    merge_node
)


def create_legal_graph():
    workflow = StateGraph(GraphState)

    # Every node execution becomes a `node.<name>` span on the active trace.
    workflow.add_node("policy_gate", traced_node("policy_gate")(policy_gate_node))
    workflow.add_node("ingestion", traced_node("ingestion")(ingestion_node))
    workflow.add_node("router", traced_node("router")(router_node))
    workflow.add_node("retrieval", traced_node("retrieval")(retrieval_node))
    workflow.add_node("analyze_question", traced_node("analyze_question")(analyze_question))
    workflow.add_node("merge", traced_node("merge")(merge_node))

    # Verdict-seeking questions are refused before any parsing or model call.
    workflow.set_entry_point("policy_gate")
    workflow.add_conditional_edges(
        "policy_gate",
        lambda state: "end" if state.get("policy_refusal") else "ingest",
        {"end": END, "ingest": "ingestion"},
    )
    workflow.add_edge("ingestion", "router")
    workflow.add_conditional_edges(
        "router",
        lambda state: "end" if not state["is_legal_doc"] else "retrieve",
        {"end": END, "retrieve": "retrieval"},
    )
    # Topics the document never mentions get a "document is silent" answer, no model call.
    workflow.add_conditional_edges(
        "retrieval",
        lambda state: "end" if state.get("document_silent") else "analyze",
        {"end": END, "analyze": "analyze_question"},
    )
    workflow.add_edge("analyze_question", "merge")
    workflow.add_edge("merge", END)

    return workflow.compile()


legal_graph = create_legal_graph()
