"""Regression tests for structured RFP conflict arbitration."""

from __future__ import annotations

from data.pipelines.rfp_intake.conflicts import (
    arbitrate_conflicts,
    detect_conflicts,
)


def test_currency_conflict_routes_to_fixed_arbiter() -> None:
    """Currency mismatch is detected from structured commitments."""

    conflicts = detect_conflicts(
        client_country="Spain",
        active_departments=[
            "warehouse",
            "reverse",
        ],
        section_commitments={
            "warehouse": {
                "currency": "EUR",
            },
            "reverse": {
                "currency": "USD",
            },
        },
    )

    assert len(conflicts) == 1

    conflict = conflicts[0]

    assert conflict["trigger_id"] == "currency-mismatch"
    assert conflict["affected_departments"] == [
        "reverse",
    ]
    assert conflict["expected_currency"] == "EUR"
    assert conflict["arbiter"] == "Miguel Torres"

    arbitration = arbitrate_conflicts(
        conflicts
    )

    assert len(arbitration) == 1

    result = arbitration[0]

    assert result["trigger_id"] == "currency-mismatch"
    assert result["action"] == "request_changes"
    assert result["affected_departments"] == [
        "reverse",
    ]
    assert result["arbiter"] == "Miguel Torres"
    assert (
        result["required_change"]
        == "Use EUR for all client-facing pricing."
    )


def test_returns_sla_conflict_routes_to_reverse_owner() -> None:
    """Returns under 48 hours trigger the fixed Reverse arbiter."""

    conflicts = detect_conflicts(
        client_country="Spain",
        active_departments=[
            "warehouse",
            "reverse",
        ],
        section_commitments={
            "warehouse": {
                "currency": "EUR",
            },
            "reverse": {
                "currency": "EUR",
                "returns_turnaround_hours": 24,
            },
        },
    )

    assert len(conflicts) == 1

    conflict = conflicts[0]

    assert conflict["trigger_id"] == "returns-sla-breach"
    assert conflict["affected_departments"] == [
        "reverse",
    ]
    assert conflict["arbiter"] == "Sofía Ramos"

    arbitration = arbitrate_conflicts(
        conflicts
    )

    assert len(arbitration) == 1

    result = arbitration[0]

    assert result["action"] == "request_changes"
    assert result["affected_departments"] == [
        "reverse",
    ]
    assert result["arbiter"] == "Sofía Ramos"
    assert (
        result["required_change"]
        == "Returns turnaround must be 48 hours or more."
    )


def test_capacity_conflict_routes_to_fixed_arbiter() -> None:
    """Last-mile committed volume cannot exceed warehouse capacity."""

    conflicts = detect_conflicts(
        client_country="US",
        active_departments=[
            "warehouse",
            "lastmile",
        ],
        section_commitments={
            "warehouse": {
                "currency": "USD",
                "capacity_limit": 4000,
            },
            "lastmile": {
                "currency": "USD",
                "committed_volume": 5000,
            },
        },
    )

    assert len(conflicts) == 1

    conflict = conflicts[0]

    assert conflict["trigger_id"] == "volume-vs-capacity"
    assert conflict["affected_departments"] == [
        "lastmile",
    ]
    assert conflict["warehouse_capacity"] == 4000
    assert conflict["lastmile_committed_volume"] == 5000
    assert conflict["arbiter"] == "Miguel Torres"

    arbitration = arbitrate_conflicts(
        conflicts
    )

    assert len(arbitration) == 1

    result = arbitration[0]

    assert result["action"] == "request_changes"
    assert result["affected_departments"] == [
        "lastmile",
    ]
    assert result["arbiter"] == "Miguel Torres"
