"""Department worker logic for TrackFlow RFP intake."""

from __future__ import annotations

import json

from data.pipelines.rfp_intake.config import DEPARTMENTS
from data.pipelines.rfp_intake.llm import generation_model, openai_client
from data.pipelines.rfp_intake.state import RFPIntakeState
from services.api.schemas import DepartmentKeyAspects


SYSTEM_PROMPT = """
You are a TrackFlow department intake analyst.

You receive:
1. shared RFP metadata
2. extracts relevant ONLY to your department

Your job is to identify what that department needs to know before TrackFlow
can prepare a proposal.

Never invent missing values.

If a required operational figure is missing, add it to open_questions.

Important rules:
- SKU count is not monthly order volume.
- Do not invent pallet quantities.
- Do not invent return rates.
- Do not invent carrier rates.
- Do not invent SLA commitments.
- Do not invent deadlines.
- Do not create proposal pricing in Part 1.
- Only ask questions that are materially necessary to scope, price,
  capacity-plan, or implement the requested service.
- Do not generate speculative questions just because they could theoretically
  be useful.
- Do not ask for derived figures that were never implied by the RFP.
- For example, do not ask for "average pallets per SKU" unless the document
  explicitly establishes pallets as relevant to the requested scope.

Return ONLY valid JSON:

{
  "requested_scope": [],
  "known_requirements": [],
  "quantitative_requirements": {},
  "open_questions": [],
  "relevant_extracts": []
}
""".strip()


DEPARTMENT_GUIDANCE = {
    "warehouse": """
Focus on:
- storage / warehousing scope
- SKU or pallet information only when explicitly present
- warehouse location
- monthly volume only when actually provided
- onboarding timing
- integrations
- special handling
- missing capacity information that is materially necessary
""".strip(),

    "lastmile": """
Focus on:
- shipping / last-mile scope
- shipment volume
- destination geography
- carrier selection needs
- delivery requirements
- missing SLA or carrier requirements
""".strip(),

    "reverse": """
Focus on:
- returns processing
- inspection
- reconditioning
- restocking
- returns volume if actually provided
- turnaround expectations
- missing returns-rate information
""".strip(),
}


def analyze_department(
    department_id: str,
    metadata: dict,
    extracts: list[str],
) -> DepartmentKeyAspects:
    """Run one department worker."""

    if department_id not in DEPARTMENTS:
        raise ValueError(
            f"Unknown TrackFlow department: {department_id}"
        )

    owner = DEPARTMENTS[department_id]["owner"]

    user_prompt = f"""
DEPARTMENT:
{department_id}

DEPARTMENT OWNER:
{owner}

DEPARTMENT GUIDANCE:
{DEPARTMENT_GUIDANCE[department_id]}

SHARED RFP METADATA:
{json.dumps(metadata, ensure_ascii=False)}

DEPARTMENT-RELEVANT EXTRACTS:
{json.dumps(extracts, ensure_ascii=False)}

Analyze only this department's responsibilities.
""".strip()

    response = openai_client().chat.completions.create(
        model=generation_model(),
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content

    if not content:
        raise RuntimeError(
            f"{department_id} worker returned an empty response."
        )

    raw = json.loads(content)

    return DepartmentKeyAspects(
        department_id=department_id,
        owner=owner,
        requested_scope=raw.get(
            "requested_scope",
            [],
        ),
        known_requirements=raw.get(
            "known_requirements",
            [],
        ),
        quantitative_requirements=raw.get(
            "quantitative_requirements",
            {},
        ),
        open_questions=raw.get(
            "open_questions",
            [],
        ),
        relevant_extracts=raw.get(
            "relevant_extracts",
            extracts,
        ),
    )


def department_worker_node(
    state: RFPIntakeState,
) -> RFPIntakeState:
    """
    Run one worker branch created by LangGraph fan-out.

    Each branch receives:
    - shared RFP metadata
    - one department_id
    - only that department's relevant extracts
    """

    department_id = state.get("department_id")

    if not department_id:
        raise ValueError(
            "Department worker received no department_id."
        )

    result = analyze_department(
        department_id=department_id,
        metadata=state.get(
            "rfp_metadata",
            {},
        ),
        extracts=state.get(
            "department_extract",
            [],
        ),
    )

    return {
        "department_results": {
            department_id: result.model_dump(
                mode="json"
            )
        }
    }


def run_department_workers(
    state: RFPIntakeState,
) -> RFPIntakeState:
    """
    Sequential helper useful for direct testing.

    The production LangGraph uses department_worker_node with fan-out
    so active departments can run in parallel.
    """

    metadata = state.get(
        "rfp_metadata",
        {},
    )

    active_departments = state.get(
        "active_departments",
        [],
    )

    department_extracts = state.get(
        "department_extracts",
        {},
    )

    results: dict[str, dict] = {}

    for department_id in active_departments:
        result = analyze_department(
            department_id=department_id,
            metadata=metadata,
            extracts=department_extracts.get(
                department_id,
                [],
            ),
        )

        results[department_id] = result.model_dump(
            mode="json"
        )

    return {
        "department_results": results,
    }