"""Minimal state shared between TrackFlow LangGraph agent nodes."""

from __future__ import annotations

from typing import Any, Literal, TypedDict


class AgentState(TypedDict, total=False):
    """Explicit state passed between LangGraph nodes."""

    question: str
    chunks: list[dict[str, Any]]
    context: str
    answer: str
    error: str | None
    run_id: str

    route: Literal["rag", "ticket", "both"]
    incident_id: int | None
    ticket_result: dict[str, Any] | None
