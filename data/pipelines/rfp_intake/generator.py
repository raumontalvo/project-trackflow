from __future__ import annotations

import json

from data.pipelines.rfp_intake.config import DEPARTMENTS
from data.pipelines.rfp_intake.evaluation import expected_currency
from data.pipelines.rfp_intake.llm import generation_model, openai_client


GENERATOR_SYSTEM_PROMPT = """
You are a TrackFlow pricing proposal generator.

You generate exactly one proposal section for one department.

Use only facts present in the RFP metadata and that department's Part 1
key_aspects. Never invent missing operational figures.

Rules:
- Pricing currency must match the client's country.
- Every section must state TrackFlow's on-time delivery SLA as a percentage.
- Never promise returns processing in under 48 hours.
- Include a volume-based discount tier table.
- Never disclose negotiated carrier rates.
- Only show final client-facing pricing.
- If evaluator feedback is provided, revise specifically to address it.

Return only the proposal section as plain text.
""".strip()


WAREHOUSE_GUIDANCE = """
You are the Warehouse Operations proposal generator.

Include:
- warehousing scope
- storage/capacity requirements supported by the RFP
- onboarding or integration requirements when known
- client-facing pricing structure in the correct currency
- volume discount tiers
- SLA statement
- unresolved open questions when needed
""".strip()


LASTMILE_GUIDANCE = """
You are the Last Mile and Carrier Management proposal generator.

Include:
- shipment and destination scope
- carrier-management requirements
- delivery SLA percentage
- client-facing shipment pricing in the correct currency
- volume discount tiers
- no negotiated carrier-rate disclosure
- unresolved open questions when needed
""".strip()


REVERSE_GUIDANCE = """
You are the Reverse Logistics proposal generator.

Include:
- returns inspection, reconditioning, and restocking scope
- returns turnaround of 48 hours or more
- client-facing returns processing pricing in the correct currency
- volume discount tiers
- SLA statement
- unresolved open questions when needed
""".strip()


def _generate_section(
    department_id: str,
    guidance: str,
    metadata: dict,
    key_aspects: dict,
    feedback: str | None = None,
) -> str:
    currency = expected_currency(
        metadata.get("client_country")
    )

    user_prompt = f"""
DEPARTMENT:
{department_id}

DEPARTMENT OWNER:
{DEPARTMENTS[department_id]["owner"]}

EXPECTED CURRENCY:
{currency}

DEPARTMENT-SPECIFIC GENERATOR INSTRUCTIONS:
{guidance}

RFP METADATA:
{json.dumps(metadata, ensure_ascii=False)}

PART 1 KEY ASPECTS:
{json.dumps(key_aspects, ensure_ascii=False)}

EVALUATOR FEEDBACK:
{feedback or "None - this is the first generation attempt."}

Draft this department's pricing proposal section.
""".strip()

    response = openai_client().chat.completions.create(
        model=generation_model(),
        messages=[
            {
                "role": "system",
                "content": GENERATOR_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        temperature=0,
    )

    content = response.choices[0].message.content

    if not content:
        raise RuntimeError(
            f"{department_id} generator returned an empty response."
        )

    return content.strip()


def generate_warehouse_section(
    metadata: dict,
    key_aspects: dict,
    feedback: str | None = None,
) -> str:
    return _generate_section(
        department_id="warehouse",
        guidance=WAREHOUSE_GUIDANCE,
        metadata=metadata,
        key_aspects=key_aspects,
        feedback=feedback,
    )


def generate_lastmile_section(
    metadata: dict,
    key_aspects: dict,
    feedback: str | None = None,
) -> str:
    return _generate_section(
        department_id="lastmile",
        guidance=LASTMILE_GUIDANCE,
        metadata=metadata,
        key_aspects=key_aspects,
        feedback=feedback,
    )


def generate_reverse_section(
    metadata: dict,
    key_aspects: dict,
    feedback: str | None = None,
) -> str:
    return _generate_section(
        department_id="reverse",
        guidance=REVERSE_GUIDANCE,
        metadata=metadata,
        key_aspects=key_aspects,
        feedback=feedback,
    )


DEPARTMENT_GENERATORS = {
    "warehouse": generate_warehouse_section,
    "lastmile": generate_lastmile_section,
    "reverse": generate_reverse_section,
}


def generate_department_section(
    department_id: str,
    metadata: dict,
    key_aspects: dict,
    feedback: str | None = None,
) -> str:
    if department_id not in DEPARTMENT_GENERATORS:
        raise ValueError(
            f"Unknown TrackFlow department: {department_id}"
        )

    generator = DEPARTMENT_GENERATORS[
        department_id
    ]

    return generator(
        metadata=metadata,
        key_aspects=key_aspects,
        feedback=feedback,
    )