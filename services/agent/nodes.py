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
from services.agent.authorization import authorize_tracking_number
from services.agent.guardrails import (
    enforce_country_policy,
    evaluate_input,
    validate_output,
)
from services.agent.state import AgentState
from services.agent.tools import TicketLookupInput, lookup_ticket


TICKET_PATTERN = re.compile(
    r"\b(?:ticket|incident)\s*#?\s*(\d+)\b",
    re.IGNORECASE,
)

TRACKING_PATTERN = re.compile(
    r"\b(?:tracking(?:\s+number)?|order)\s*#\s*([A-Za-z0-9-]+)\b"
    r"|\btracking(?:\s+number)?\s+([A-Za-z0-9-]*\d[A-Za-z0-9-]*)\b"
    r"|\border\s+([A-Za-z0-9-]*\d[A-Za-z0-9-]*)\b",
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


def guard_input_node(state: AgentState) -> AgentState:
    """Apply deterministic scope, content, and anti-injection guardrails."""
    decision = evaluate_input(state["question"])

    return {
        "guardrail_allowed": decision.allowed,
        "guardrail_category": decision.category,
        "guardrail_reason": decision.reason,
        "guardrail_response": decision.response,
        "answer": decision.response if not decision.allowed else None,
    }


def tracking_authorization_node(state: AgentState) -> AgentState:
    """Authorize access to any tracking/order number mentioned by the user."""
    question = state["question"]
    match = TRACKING_PATTERN.search(question)

    if not match:
        return {
            "tracking_number": None,
            "tracking_authorized": None,
            "tracking_authorization_reason": None,
            "shipment_country": None,
        }

    tracking_number = next(
        group for group in match.groups() if group is not None
    )

    authenticated_user_uuid = state.get("authenticated_user_uuid")

    if not authenticated_user_uuid:
        return {
            "tracking_number": tracking_number,
            "tracking_authorized": False,
            "tracking_authorization_reason": "missing_authenticated_user",
            "shipment_country": None,
            "answer": (
                "I can't verify access to that TrackFlow order or tracking "
                "number. Please authenticate with the customer account that "
                "owns the shipment."
            ),
        }

    authorization = authorize_tracking_number(
        tracking_number=tracking_number,
        authenticated_user_uuid=authenticated_user_uuid,
    )

    if not authorization.authorized:
        return {
            "tracking_number": tracking_number,
            "tracking_authorized": False,
            "tracking_authorization_reason": authorization.reason,
            "shipment_country": authorization.shipment_country,
            "answer": (
                "I can't provide information for that order or tracking "
                "number because I can't verify that it belongs to your "
                "authenticated TrackFlow account."
            ),
        }

    return {
        "tracking_number": tracking_number,
        "tracking_authorized": True,
        "tracking_authorization_reason": None,
        "shipment_country": authorization.shipment_country,
    }


def country_policy_guard_node(state: AgentState) -> AgentState:
    """Enforce the policy that belongs to the shipment's actual country."""
    decision = enforce_country_policy(
        question=state["question"],
        shipment_country=state.get("shipment_country"),
    )

    return {
        "shipment_country": (
            decision.shipment_country
            if decision.shipment_country is not None
            else state.get("shipment_country")
        ),
        "requested_policy_country": decision.requested_country,
        "country_policy_allowed": decision.allowed,
        "country_policy_reason": decision.reason,
        "country_policy_response": decision.response,
        "answer": (
            decision.response
            if not decision.allowed
            else state.get("answer")
        ),
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


def output_guard_node(state: AgentState) -> AgentState:
    """Validate the final answer before exposing it to the user."""
    decision = validate_output(state.get("answer"))

    if decision.allowed:
        return {
            "output_guard_allowed": True,
            "output_guard_failure_type": None,
            "output_guard_reason": None,
        }

    return {
        "output_guard_allowed": False,
        "output_guard_failure_type": decision.failure_type,
        "output_guard_reason": decision.reason,
        "answer": decision.safe_response,
    }


def route_after_validation(state: AgentState) -> str:
    """Route invalid questions directly to the end."""
    if state.get("error"):
        return "invalid"

    return "valid"


def route_after_guard(state: AgentState) -> str:
    """Route input-guard failures directly to the end."""
    if not state.get("guardrail_allowed", True):
        return "blocked"

    return "allowed"


def route_after_tracking_authorization(state: AgentState) -> str:
    """Stop unauthorized tracking requests before RAG or tools execute."""
    tracking_number = state.get("tracking_number")
    tracking_authorized = state.get("tracking_authorized")

    if tracking_number and tracking_authorized is False:
        return "blocked"

    return "allowed"


def route_after_country_policy(state: AgentState) -> str:
    """Stop country-policy override attempts before RAG or tools execute."""
    if not state.get("country_policy_allowed", True):
        return "blocked"

    return "allowed"


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


def route_after_output_guard(state: AgentState) -> str:
    """Finish after output validation, whether allowed or safely replaced."""
    if state.get("output_guard_allowed", True):
        return "allowed"

    return "blocked"