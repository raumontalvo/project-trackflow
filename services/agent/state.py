"""Minimal state shared between TrackFlow LangGraph agent nodes."""

from __future__ import annotations

from typing import Any, Literal, TypedDict


class AgentState(TypedDict, total=False):
    """Explicit state passed between LangGraph nodes."""

    question: str
    chunks: list[dict[str, Any]]
    context: str
    answer: str | None
    error: str | None
    run_id: str

    authenticated_user_id: str
    authenticated_user_uuid: str

    guardrail_allowed: bool
    guardrail_category: Literal[
        "allowed",
        "casual",
        "personal_task",
        "security",
        "sensitive_data",
    ]
    guardrail_reason: str | None
    guardrail_response: str | None

    tracking_number: str | None
    tracking_authorized: bool | None
    tracking_authorization_reason: str | None

    shipment_country: Literal["USA", "Spain"] | None
    requested_policy_country: Literal["USA", "Spain"] | None
    country_policy_allowed: bool | None
    country_policy_reason: str | None
    country_policy_response: str | None

    output_guard_allowed: bool | None
    output_guard_failure_type: Literal[
        "structural",
        "content",
        "security",
    ] | None
    output_guard_reason: str | None

    route: Literal["rag", "ticket", "both"]
    incident_id: int | None
    ticket_result: dict[str, Any] | None