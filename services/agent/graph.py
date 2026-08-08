"""Compiled LangGraph workflow for the TrackFlow knowledge agent."""

from __future__ import annotations

from uuid import uuid4

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from services.agent.nodes import (
    generate_answer_node,
    generate_combined_answer_node,
    generate_ticket_answer_node,
    memory_evaluation_node,
    no_context_node,
    recall_memory_node,
    retrieve_context_node,
    resolve_pending_memory_node,
    route_after_pending_memory,
    route_after_request,
    route_after_retrieval,
    route_after_ticket_lookup,
    route_after_validation,
    route_request_node,
    ticket_fallback_node,
    ticket_lookup_node,
    validate_question_node,
)
from services.agent.state import AgentState
from services.agent.trace import record_trace


def build_graph():
    """Build and compile the TrackFlow support-agent graph."""
    builder = StateGraph(AgentState)

    builder.add_node(
        "resolve_pending_memory",
        resolve_pending_memory_node,
    )
    builder.add_node("validate_question", validate_question_node)
    builder.add_node("recall_memory", recall_memory_node)
    builder.add_node("route_request", route_request_node)
    builder.add_node("retrieve_context", retrieve_context_node)
    builder.add_node("ticket_lookup", ticket_lookup_node)
    builder.add_node("ticket_fallback", ticket_fallback_node)
    builder.add_node("no_context", no_context_node)
    builder.add_node("generate_answer", generate_answer_node)
    builder.add_node("generate_ticket_answer", generate_ticket_answer_node)
    builder.add_node("generate_combined_answer", generate_combined_answer_node)
    builder.add_node("memory_evaluation", memory_evaluation_node)

    builder.add_edge(START, "resolve_pending_memory")

    builder.add_conditional_edges(
        "resolve_pending_memory",
        route_after_pending_memory,
        {
            "continue": "validate_question",
            "resolved": END,
        },
    )

    builder.add_conditional_edges(
        "validate_question",
        route_after_validation,
        {
            "valid": "recall_memory",
            "invalid": END,
        },
    )

    builder.add_edge("recall_memory", "route_request")

    builder.add_conditional_edges(
        "route_request",
        route_after_request,
        {
            "rag": "retrieve_context",
            "ticket": "ticket_lookup",
            "both": "ticket_lookup",
        },
    )

    builder.add_conditional_edges(
        "ticket_lookup",
        route_after_ticket_lookup,
        {
            "ticket": "generate_ticket_answer",
            "both": "retrieve_context",
            "failed": "ticket_fallback",
        },
    )

    builder.add_conditional_edges(
        "retrieve_context",
        route_after_retrieval,
        {
            "context_found": "generate_answer",
            "combined": "generate_combined_answer",
            "no_context": "no_context",
        },
    )

    builder.add_edge("generate_answer", "memory_evaluation")
    builder.add_edge("generate_ticket_answer", "memory_evaluation")
    builder.add_edge("generate_combined_answer", "memory_evaluation")
    builder.add_edge("ticket_fallback", "memory_evaluation")
    builder.add_edge("no_context", "memory_evaluation")

    builder.add_edge("memory_evaluation", END)

    checkpointer = MemorySaver()

    return builder.compile(checkpointer=checkpointer)


agent_graph = build_graph()


async def run_agent(
    question: str,
    conversation_id: str | None = None,
) -> AgentState:
    """Run the graph with stable conversation state and a unique trace run."""

    run_id = str(uuid4())
    conversation_id = conversation_id or str(uuid4())

    initial_state: AgentState = {
        "question": question,
        "conversation_id": conversation_id,
        "run_id": run_id,

        # Reset transient per-turn fields so checkpointed state from the
        # previous message cannot leak into the new request.
        "chunks": [],
        "context": "",
        "answer": "",
        "error": None,
        "incident_id": None,
        "ticket_result": None,
        "memory_proposal": None,
        "memory_decision": None,
        "memory_status": None,
        "memory_notice": "",
        "recalled_memories": [],
        "memory_context": "",
    }

    config = {
        "configurable": {
            "thread_id": conversation_id,
        }
    }

    events: list[dict] = []
    final_state: AgentState = initial_state.copy()

    async for event in agent_graph.astream(
        initial_state,
        config=config,
        stream_mode="updates",
    ):
        for node_name, update in event.items():
            events.append(
                {
                    "node": node_name,
                    "output": update,
                }
            )

            if isinstance(update, dict):
                final_state.update(update)

    record_trace(
        run_id=run_id,
        question=question,
        result=final_state,
        events=events,
    )

    return final_state
