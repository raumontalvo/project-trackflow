"""Shared state for the TrackFlow RFP intake LangGraph workflow."""

from __future__ import annotations

from typing import Annotated, Any, TypedDict


def merge_department_results(
    left: dict[str, dict[str, Any]] | None,
    right: dict[str, dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    """Merge results produced by parallel department workers."""

    merged = dict(left or {})
    merged.update(right or {})
    return merged


class RFPIntakeState(TypedDict, total=False):
    """State passed between RFP intake workflow nodes."""

    # Persisted identifiers
    ticket_id: str
    rfp_id: str | None

    # Source document
    raw_pdf_path: str
    markdown: str

    # Classification
    classification: dict[str, Any]
    is_rfp: bool
    rejection_reason: str | None

    # Extracted RFP information
    rfp_metadata: dict[str, Any]
    readability_metrics: dict[str, Any]

    # Department routing
    active_departments: list[str]
    department_extracts: dict[str, list[str]]

    # Used by an individual fan-out worker branch
    department_id: str
    department_extract: list[str]

    # Parallel worker results must merge rather than overwrite each other
    department_results: Annotated[
        dict[str, dict[str, Any]],
        merge_department_results,
    ]

    # Final Sales-facing result
    summary: dict[str, Any]

    # Workflow outcome
    status: str
    error: str | None