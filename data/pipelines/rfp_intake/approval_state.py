"""State for TrackFlow Part 3 approval and completion workflow."""

from __future__ import annotations

from typing import Annotated, Any, TypedDict


def merge_department_approvals(
    left: dict[str, dict[str, Any]] | None,
    right: dict[str, dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    """Merge approval updates produced by parallel department branches."""

    merged = dict(left or {})
    merged.update(right or {})
    return merged




def merge_section_updates(
    left: dict[str, dict[str, Any]] | None,
    right: dict[str, dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    """Merge per-department section updates from parallel branches."""

    merged = dict(left or {})
    merged.update(right or {})
    return merged

def merge_revision_counts(
    left: dict[str, int] | None,
    right: dict[str, int] | None,
) -> dict[str, int]:
    """Merge revision counters from independent department branches."""

    merged = dict(left or {})
    merged.update(right or {})
    return merged

def merge_trace_events(
    left: list[dict[str, Any]] | None,
    right: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Append workflow trace events without losing branch history."""

    return [*(left or []), *(right or [])]


class RFPApprovalState(TypedDict, total=False):
    """Shared state for TrackFlow Part 3."""

    ticket_id: str
    rfp_id: str

    client_name: str | None
    client_country: str | None
    currency: str

    active_departments: list[str]

    sections: Annotated[
        dict[str, dict[str, Any]],
        merge_section_updates,
    ]
    section_commitments: Annotated[
        dict[str, dict[str, Any]],
        merge_section_updates,
    ]
    revision_counts: Annotated[
        dict[str, int],
        merge_revision_counts,
    ]

    # Branch-scoped values
    department_id: str
    section: dict[str, Any]

    # Department-thread routing state
    entry_action: str
    decision_action: str
    revision_outcome: str

    approval_branch_department: str
    approval_branch_action: str

    # Parallel approval branches merge here
    approval_results: Annotated[
        dict[str, dict[str, Any]],
        merge_department_approvals,
    ]

    # Structured conflict/arbitration state
    conflicts: list[dict[str, Any]]
    arbitration_results: list[dict[str, Any]]

    # Execution trace
    trace_events: Annotated[
        list[dict[str, Any]],
        merge_trace_events,
    ]

    final_document: dict[str, Any] | None

    status: str
    error: str | None
