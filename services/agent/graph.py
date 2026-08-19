"""Compiled LangGraph workflow for the TrackFlow knowledge agent."""

from __future__ import annotations

from uuid import uuid4

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from services.agent.nodes import (
    generate_answer_node,
    generate_combined_answer_node,
    generate_ticket_answer_node,
    no_context_node,
    retrieve_context_node,
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

    builder.add_node("validate_question", validate_question_node)
    builder.add_node("route_request", route_request_node)
    builder.add_node("retrieve_context", retrieve_context_node)
    builder.add_node("ticket_lookup", ticket_lookup_node)
    builder.add_node("ticket_fallback", ticket_fallback_node)
    builder.add_node("no_context", no_context_node)
    builder.add_node("generate_answer", generate_answer_node)
    builder.add_node("generate_ticket_answer", generate_ticket_answer_node)
    builder.add_node("generate_combined_answer", generate_combined_answer_node)

    builder.add_edge(START, "validate_question")

    builder.add_conditional_edges(
        "validate_question",
        route_after_validation,
        {
            "valid": "route_request",
            "invalid": END,
        },
    )

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

    builder.add_edge("generate_answer", END)
    builder.add_edge("generate_ticket_answer", END)
    builder.add_edge("generate_combined_answer", END)
    builder.add_edge("ticket_fallback", END)
    builder.add_edge("no_context", END)

    checkpointer = MemorySaver()

    return builder.compile(checkpointer=checkpointer)


agent_graph = build_graph()


async def run_agent(question: str) -> AgentState:
    """Run the compiled graph asynchronously and persist a structured trace."""
    run_id = str(uuid4())

    initial_state: AgentState = {
        "question": question,
        "run_id": run_id,
    }

    config = {
        "configurable": {
            "thread_id": run_id,
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
