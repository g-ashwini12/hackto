from langgraph.graph import StateGraph, END
from services.api.app.orchestrator.state import GraphState
from services.api.app.orchestrator.nodes import (
    ingestion_node,
    router_node,
    retrieval_node,
    analyze_question,
    merge_node
)

def create_legal_graph():
    workflow = StateGraph(GraphState)

    # Add Nodes
    workflow.add_node("ingestion", ingestion_node)
    workflow.add_node("router", router_node)
    workflow.add_node("retrieval", retrieval_node)
    workflow.add_node("analyze_question", analyze_question)
    workflow.add_node("merge", merge_node)

    # Set Entry
    workflow.set_entry_point("ingestion")

    # Edges
    workflow.add_edge("ingestion", "router")

    # Conditional Routing
    workflow.add_conditional_edges(
        "router",
        lambda state: "end" if not state["is_legal_doc"] else "retrieve",
        {
            "end": END,
            "retrieve": "retrieval"
        }
    )

    workflow.add_edge("retrieval", "analyze_question")
    workflow.add_edge("analyze_question", "merge")
    workflow.add_edge("merge", END)

    return workflow.compile()

legal_graph = create_legal_graph()
