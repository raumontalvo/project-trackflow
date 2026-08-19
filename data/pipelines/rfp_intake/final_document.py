"""TrackFlow final proposal synthesis."""

from __future__ import annotations

from typing import Any


DEPARTMENT_TITLES = {
    "warehouse": "Warehouse Operations",
    "lastmile": "Last Mile and Carrier Management",
    "reverse": "Reverse Logistics",
}


def synthesize_final_document(
    *,
    client_name: str | None,
    currency: str,
    active_departments: list[str],
    sections: dict[str, dict[str, Any]],
) -> tuple[str, dict[str, str]]:
    """
    Consolidate already-approved sections without changing their terms.

    The synthesizer does not renegotiate, rewrite pricing, or invent facts.
    """

    approved_sections: dict[str, str] = {}

    body: list[str] = [
        f"# TrackFlow Proposal — {client_name or 'Client'}",
        "",
        f"**Currency:** {currency}",
        "",
        "This proposal contains the department sections approved through "
        "TrackFlow's RFP approval workflow.",
        "",
    ]

    for department_id in active_departments:
        section = sections.get(
            department_id,
            {},
        )

        draft = section.get(
            "draft_content"
        )

        if not draft:
            raise ValueError(
                f"Missing approved draft for {department_id}."
            )

        approved_sections[
            department_id
        ] = draft

        title = DEPARTMENT_TITLES.get(
            department_id,
            department_id,
        )

        body.extend(
            [
                f"## {title}",
                "",
                draft,
                "",
            ]
        )

    return (
        "\n".join(body).strip(),
        approved_sections,
    )
