"""Single-responsibility nodes for the TrackFlow LangGraph agent."""

from __future__ import annotations

from data.pipelines.rag import (
    DEFAULT_SCORE_THRESHOLD,
    DEFAULT_TOP_K,
    NO_CONTEXT_ANSWER,
    build_context,
    generate_answer,
    retrieve,
)
from services.agent.state import AgentState


def validate_question_node(state: AgentState) -> AgentState:
    """Validate and normalize the incoming question."""
    question = state.get("question", "").strip()

    if not question:
        return {
            "question": "",
            "error": "Question cannot be empty.",
            "answer": "",
        }

    return {
        "question": question,
        "error": None,
    }


def retrieve_context_node(state: AgentState) -> AgentState:
    """Retrieve and format approved TrackFlow knowledge-base context."""
    question = state["question"]

    chunks = retrieve(
        question,
        k=DEFAULT_TOP_K,
        min_score=DEFAULT_SCORE_THRESHOLD,
    )

    context = build_context(chunks)

    return {
        "chunks": chunks,
        "context": context,
    }


def no_context_node(state: AgentState) -> AgentState:
    """Return the existing safe fallback when retrieval finds no context."""
    return {
        "answer": NO_CONTEXT_ANSWER,
    }


def generate_answer_node(state: AgentState) -> AgentState:
    """Generate from context already produced by the retrieval node."""
    question = state["question"]
    context = state.get("context", "")

    answer = generate_answer(question, context)

    return {
        "answer": answer,
    }


def route_after_validation(state: AgentState) -> str:
    """Route invalid questions directly to the end."""
    if state.get("error"):
        return "invalid"

    return "valid"


def route_after_retrieval(state: AgentState) -> str:
    """Route based on whether relevant context was retrieved."""
    if state.get("context"):
        return "context_found"

    return "no_context"