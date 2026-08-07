"""Single-responsibility nodes for the TrackFlow LangGraph agent."""

from __future__ import annotations

import re

from data.pipelines.rag import (
    DEFAULT_SCORE_THRESHOLD,
    DEFAULT_TOP_K,
    NO_CONTEXT_ANSWER,
    build_context,
    generate_answer,
    retrieve,
)
from services.agent.state import AgentState
from services.agent.tools import TicketLookupInput, lookup_ticket


TICKET_PATTERN = re.compile(
    r"\b(?:ticket|incident)\s*#?\s*(\d+)\b",
    re.IGNORECASE,
)


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


def route_request_node(state: AgentState) -> AgentState:
    """Classify whether the request needs RAG, a ticket lookup, or both."""
    question = state["question"]
    match = TICKET_PATTERN.search(question)

    if not match:
        return {
            "route": "rag",
            "incident_id": None,
        }

    incident_id = int(match.group(1))

    policy_terms = (
        "policy",
        "procedure",
        "according to",
        "what should",
        "how should",
        "escalat",
        "return",
        "sla",
    )

    route = (
        "both"
        if any(term in question.lower() for term in policy_terms)
        else "ticket"
    )

    return {
        "route": route,
        "incident_id": incident_id,
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


async def ticket_lookup_node(state: AgentState) -> AgentState:
    """Query current ticket data through the TrackFlow MCP server."""
    incident_id = state.get("incident_id")

    if incident_id is None:
        return {
            "ticket_result": None,
            "error": "No incident ID was provided for ticket lookup.",
        }

    result = await lookup_ticket(
        TicketLookupInput(
            incident_id=incident_id,
        )
    )

    return {
        "ticket_result": result.model_dump(mode="json"),
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


def generate_ticket_answer_node(state: AgentState) -> AgentState:
    """Generate a deterministic answer from live incident data."""
    ticket_result = state.get("ticket_result") or {}
    incident = ticket_result["incident"]

    return {
        "answer": (
            f"Incident {incident['id']} is currently "
            f"{incident['status'].replace('_', ' ')}. "
            f"Title: {incident['title']}. "
            f"Branch: {incident['branch']}."
        )
    }


def ticket_fallback_node(state: AgentState) -> AgentState:
    """Return a safe deterministic answer when the incident tool fails."""
    ticket_result = state.get("ticket_result") or {}

    return {
        "answer": (
            ticket_result.get("error")
            or "I could not confirm the current incident status."
        )
    }


def generate_combined_answer_node(state: AgentState) -> AgentState:
    """Answer using both live incident data and approved RAG context."""
    ticket_result = state.get("ticket_result") or {}
    incident = ticket_result["incident"]
    context = state.get("context", "")

    combined_context = (
        "LIVE INCIDENT DATA:\n"
        f"ID: {incident['id']}\n"
        f"Title: {incident['title']}\n"
        f"Description: {incident['description']}\n"
        f"Category: {incident['category']}\n"
        f"Status: {incident['status']}\n"
        f"Origin: {incident['origin']}\n"
        f"Branch: {incident['branch']}\n\n"
        "KNOWLEDGE BASE CONTEXT:\n"
        f"{context}"
    )

    answer = generate_answer(
        state["question"],
        combined_context,
    )

    return {
        "answer": answer,
    }


def route_after_validation(state: AgentState) -> str:
    """Route invalid questions directly to the end."""
    if state.get("error"):
        return "invalid"

    return "valid"


def route_after_request(state: AgentState) -> str:
    """Route the request to the appropriate capability."""
    return state.get("route", "rag")


def route_after_retrieval(state: AgentState) -> str:
    """Route based on retrieved context and requested capability."""
    if not state.get("context"):
        return "no_context"

    if state.get("route") == "both":
        return "combined"

    return "context_found"


def route_after_ticket_lookup(state: AgentState) -> str:
    """Route successful tool calls onward and failures to recovery."""
    ticket_result = state.get("ticket_result") or {}

    if not ticket_result.get("success"):
        return "failed"

    if state.get("route") == "both":
        return "both"

    return "ticket"
