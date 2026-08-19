"""Compiled LangGraph workflow for the TrackFlow knowledge agent."""

from __future__ import annotations

from uuid import uuid4

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from services.agent.nodes import (
    generate_answer_node,
    no_context_node,
    retrieve_context_node,
    route_after_retrieval,
    route_after_validation,
    validate_question_node,
)
from services.agent.state import AgentState
from services.agent.trace import record_trace


def build_graph():
    """Build and compile the TrackFlow agent graph."""
    builder = StateGraph(AgentState)

    builder.add_node("validate_question", validate_question_node)
    builder.add_node("retrieve_context", retrieve_context_node)
    builder.add_node("no_context", no_context_node)
    builder.add_node("generate_answer", generate_answer_node)

    builder.add_edge(START, "validate_question")

    builder.add_conditional_edges(
        "validate_question",
        route_after_validation,
        {
            "valid": "retrieve_context",
            "invalid": END,
        },
    )

    builder.add_conditional_edges(
        "retrieve_context",
        route_after_retrieval,
        {
            "context_found": "generate_answer",
            "no_context": "no_context",
        },
    )

    builder.add_edge("generate_answer", END)
    builder.add_edge("no_context", END)

    checkpointer = MemorySaver()

    return builder.compile(checkpointer=checkpointer)


agent_graph = build_graph()


def run_agent(question: str) -> AgentState:
    """Run the compiled graph and persist a structured trace."""
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

    for event in agent_graph.stream(
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