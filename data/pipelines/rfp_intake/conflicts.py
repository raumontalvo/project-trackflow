"""Deterministic TrackFlow Part 3 conflict detection and arbitration."""

from __future__ import annotations

from typing import Any

from data.pipelines.rfp_intake.evaluation import expected_currency


VOLUME_VS_CAPACITY = "volume-vs-capacity"
RETURNS_SLA_BREACH = "returns-sla-breach"
CURRENCY_MISMATCH = "currency-mismatch"

MAX_ARBITRATION_ITERATIONS = 3


def _number(value: Any) -> float | None:
    """Convert a structured numeric value when possible."""

    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        cleaned = (
            value.replace(",", "")
            .replace("~", "")
            .strip()
        )

        try:
            return float(cleaned)
        except ValueError:
            return None

    return None


def detect_conflicts(
    *,
    client_country: str | None,
    active_departments: list[str],
    section_commitments: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Detect TrackFlow Part 3 conflicts from structured state only.

    No LLM arbitration and no free-text voting are used here.
    """

    conflicts: list[dict[str, Any]] = []

    expected = expected_currency(client_country)

    # ---------------------------------------------------------------
    # currency-mismatch
    # ---------------------------------------------------------------

    currencies: dict[str, str] = {}

    for department_id in active_departments:
        commitments = section_commitments.get(
            department_id,
            {},
        )

        currency = commitments.get("currency")

        if currency:
            currencies[department_id] = str(currency).upper()

    wrong_currency_departments = [
        department_id
        for department_id, currency in currencies.items()
        if expected and currency != expected
    ]

    distinct_currencies = set(currencies.values())

    if (
        wrong_currency_departments
        or len(distinct_currencies) > 1
    ):
        conflicts.append(
            {
                "trigger_id": CURRENCY_MISMATCH,
                "arbiter": "Miguel Torres",
                "expected_currency": expected,
                "currencies": currencies,
                "affected_departments": sorted(
                    wrong_currency_departments
                    if expected
                    else currencies.keys()
                ),
                "resolution": (
                    "Rewrite offending sections to the client-country "
                    "currency; reject if unresolved after iteration limit."
                ),
            }
        )

    # ---------------------------------------------------------------
    # returns-sla-breach
    # ---------------------------------------------------------------

    returns_offenders: list[str] = []

    for department_id in active_departments:
        commitments = section_commitments.get(
            department_id,
            {},
        )

        turnaround = _number(
            commitments.get(
                "returns_turnaround_hours"
            )
        )

        if (
            turnaround is not None
            and turnaround < 48
        ):
            returns_offenders.append(
                department_id
            )

    if returns_offenders:
        arbiter = (
            "Sofía Ramos"
            if set(returns_offenders) == {"reverse"}
            else "Miguel Torres"
        )

        conflicts.append(
            {
                "trigger_id": RETURNS_SLA_BREACH,
                "arbiter": arbiter,
                "affected_departments": sorted(
                    returns_offenders
                ),
                "resolution": (
                    "Force request_changes on every section promising "
                    "returns processing under 48 hours."
                ),
            }
        )

    # ---------------------------------------------------------------
    # volume-vs-capacity
    # ---------------------------------------------------------------

    if (
        "warehouse" in active_departments
        and "lastmile" in active_departments
    ):
        warehouse = section_commitments.get(
            "warehouse",
            {},
        )

        lastmile = section_commitments.get(
            "lastmile",
            {},
        )

        capacity = _number(
            warehouse.get("capacity_limit")
        )

        quoted_volume = _number(
            lastmile.get("committed_volume")
        )

        if (
            capacity is not None
            and quoted_volume is not None
            and quoted_volume > capacity
        ):
            conflicts.append(
                {
                    "trigger_id": VOLUME_VS_CAPACITY,
                    "arbiter": "Miguel Torres",
                    "warehouse_capacity": capacity,
                    "lastmile_committed_volume": quoted_volume,
                    "affected_departments": [
                        "lastmile",
                    ],
                    "resolution": (
                        "Cap proposal volume to warehouse capacity and "
                        "require lastmile to revise quoted volume/cost "
                        "downward."
                    ),
                }
            )

    return conflicts


def arbitrate_conflicts(
    conflicts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Apply TrackFlow's fixed arbitration rules.

    This function does not ask an LLM to choose a winner.
    """

    results: list[dict[str, Any]] = []

    for conflict in conflicts:
        trigger_id = conflict["trigger_id"]

        if trigger_id == RETURNS_SLA_BREACH:
            results.append(
                {
                    "trigger_id": trigger_id,
                    "arbiter": conflict["arbiter"],
                    "action": "request_changes",
                    "affected_departments": conflict[
                        "affected_departments"
                    ],
                    "required_change": (
                        "Returns turnaround must be 48 hours or more."
                    ),
                }
            )

        elif trigger_id == CURRENCY_MISMATCH:
            results.append(
                {
                    "trigger_id": trigger_id,
                    "arbiter": "Miguel Torres",
                    "action": "request_changes",
                    "affected_departments": conflict[
                        "affected_departments"
                    ],
                    "required_change": (
                        "Use "
                        f"{conflict.get('expected_currency')} "
                        "for all client-facing pricing."
                    ),
                }
            )

        elif trigger_id == VOLUME_VS_CAPACITY:
            results.append(
                {
                    "trigger_id": trigger_id,
                    "arbiter": "Miguel Torres",
                    "action": "request_changes",
                    "affected_departments": [
                        "lastmile"
                    ],
                    "required_change": (
                        "Cap last-mile committed volume at "
                        f"{conflict['warehouse_capacity']:g} "
                        "and revise pricing accordingly."
                    ),
                }
            )

        else:
            raise ValueError(
                f"Unknown TrackFlow conflict trigger: {trigger_id}"
            )

    return results