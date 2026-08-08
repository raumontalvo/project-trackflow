"""Orchestrator node for TrackFlow RFP department workstreams."""

from __future__ import annotations

import json

from data.pipelines.rfp_intake.config import DEPARTMENTS
from data.pipelines.rfp_intake.llm import generation_model, openai_client
from data.pipelines.rfp_intake.state import RFPIntakeState


SYSTEM_PROMPT = """
You are the TrackFlow RFP intake orchestrator.

The active departments have ALREADY been determined by application logic.
You must not add, remove, rename, or invent departments.

Your job is to isolate only the document information relevant to each active
department.

Valid departments:

warehouse:
- storage requirements
- SKU/pallet/inventory information
- warehouse location
- onboarding requirements
- warehouse integrations
- warehouse capacity needs

lastmile:
- shipping requirements
- destinations
- carrier selection
- delivery expectations
- shipment/order volume
- last-mile service requirements

reverse:
- returns
- reverse logistics
- inspection
- reconditioning
- restocking
- return turnaround expectations

Return JSON with exactly this structure:

{
  "department_extracts": {
    "warehouse": ["relevant passage", "..."],
    "lastmile": ["relevant passage", "..."],
    "reverse": ["relevant passage", "..."]
  }
}

Rules:
- Include ONLY active departments supplied by the user.
- Use information supported by the document.
- Prefer short, useful extracts rather than the entire document.
- Preserve important numbers and explicit exclusions.
- Do not invent missing information.
- Do not create proposal pricing.
- Do not resolve unanswered business questions.
""".strip()


def orchestrate_department_extracts(
    markdown: str,
    active_departments: list[str],
) -> dict[str, list[str]]:
    """Extract department-specific document slices."""

    if not markdown.strip():
        raise ValueError("Cannot orchestrate an empty RFP document.")

    if not active_departments:
        raise ValueError("No active departments were provided.")

    invalid = [
        department
        for department in active_departments
        if department not in DEPARTMENTS
    ]

    if invalid:
        raise ValueError(
            f"Unknown TrackFlow departments: {invalid}"
        )

    user_prompt = f"""
ACTIVE DEPARTMENTS:
{json.dumps(active_departments)}

RFP DOCUMENT:
----------------
{markdown.strip()}
----------------

Return department_extracts for ONLY the active departments.
""".strip()

    response = openai_client().chat.completions.create(
        model=generation_model(),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content

    if not content:
        raise RuntimeError(
            "The orchestrator returned an empty response."
        )

    raw = json.loads(content)
    raw_extracts = raw.get("department_extracts", {})

    extracts: dict[str, list[str]] = {}

    for department in active_departments:
        department_extracts = raw_extracts.get(department, [])

        if not isinstance(department_extracts, list):
            department_extracts = []

        extracts[department] = [
            str(item).strip()
            for item in department_extracts
            if str(item).strip()
        ]

    return extracts


def orchestrator_node(
    state: RFPIntakeState,
) -> RFPIntakeState:
    """LangGraph orchestrator node."""

    extracts = orchestrate_department_extracts(
        markdown=state.get("markdown", ""),
        active_departments=state.get(
            "active_departments",
            [],
        ),
    )

    return {
        "department_extracts": extracts,
    }