"""Department proposal generators for TrackFlow RFP responses."""

from __future__ import annotations

import json

from data.pipelines.rfp_intake.config import DEPARTMENTS
from data.pipelines.rfp_intake.evaluation import expected_currency
from data.pipelines.rfp_intake.llm import (
    generation_model,
    openai_client,
)


GENERATOR_SYSTEM_PROMPT = """
You are a TrackFlow pricing proposal generator.

You generate exactly one proposal section for one department.

SOURCE-OF-TRUTH RULES

Use only facts present in:
1. the RFP metadata,
2. that department's Part 1 key_aspects,
3. explicit evaluator feedback.

Never invent missing operational facts.

Do not invent:
- warehouse capacity,
- pallet positions,
- order or return volumes,
- carrier names,
- negotiated carrier rates,
- onboarding dates or durations,
- client-specific service capabilities,
- product dimensions or storage conditions,
- client-specific pricing assumptions that are not supported by input.

When information is missing, say it is pending confirmation and include it
under unresolved open questions.

COMPLIANCE RULES

- Pricing currency must match the client's country.
- Every section must state an on-time delivery SLA percentage.
- Never promise returns processing in under 48 hours.
- Include a volume-based discount tier table.
- Never disclose negotiated carrier rates.
- Only show final client-facing pricing.
- If evaluator feedback is provided, revise specifically to address it.

READABILITY RULES

Write for a commercial business reader.

- Prefer short sentences.
- Target about 12 to 18 words per sentence.
- Avoid long compound sentences.
- Use common business vocabulary.
- Use short paragraphs of 1 to 3 sentences.
- Use bullets for requirements and open questions.
- Keep section headings short.
- Avoid unnecessary adjectives and filler.
- Avoid repeating the same fact.
- Prefer active voice.
- Keep the proposal concise.

If evaluator feedback says readability is poor:
- simplify sentence structure aggressively,
- shorten paragraphs,
- split long sentences,
- remove unnecessary wording,
- preserve all required compliance information.

Return only the proposal section as plain text.
""".strip()


WAREHOUSE_GUIDANCE = """
You are the Warehouse Operations proposal generator.

Include:
- warehousing scope requested by the client,
- storage or capacity requirements only when supported by the RFP,
- onboarding or integration requirements only when known,
- client-facing pricing structure in the correct currency,
- volume discount tier table,
- on-time delivery SLA percentage,
- unresolved open questions when information is missing.

Do not claim TrackFlow has enough warehouse capacity unless structured
input explicitly supports that claim.

Do not invent pallet quantities from SKU counts.
""".strip()


LASTMILE_GUIDANCE = """
You are the Last Mile and Carrier Management proposal generator.

Keep this section concise and easy to read.

Include:
- shipment and destination scope,
- carrier-management requirements,
- on-time delivery SLA percentage,
- client-facing shipment pricing in the correct currency,
- volume discount tier table,
- no negotiated carrier-rate disclosure,
- unresolved open questions when needed,
- any known peak-season, holiday, or seasonal-volume requirement from
  key_aspects.

IMPORTANT:
If key_aspects mention holidays, peak season, seasonal demand, or expected
volume changes, explicitly acknowledge that requirement in the proposal.

For example, if the RFP says the holiday season is approaching, state that
holiday peak planning is part of the operating scope. If the actual peak
volume is unknown, do not invent it. Add the expected holiday uplift as an
open question.

Use short sentences.
Prefer bullets over dense paragraphs.

Do not invent:
- carriers,
- destinations,
- shipment volumes,
- peak-season volume increases,
- shipment weights,
- delivery speeds,
- operational commitments not present in the input.

If an exact commercial value is not supported by the input, mark it as
pending confirmation rather than presenting it as an established fact.
""".strip()


REVERSE_GUIDANCE = """
You are the Reverse Logistics proposal generator.

Include:
- returns inspection, reconditioning, and restocking scope,
- returns turnaround of 48 hours or more,
- client-facing returns processing pricing in the correct currency,
- volume discount tier table,
- on-time delivery SLA percentage,
- unresolved open questions when needed.

Never suggest or offer returns processing below 48 hours.
Do not invent return volumes or product-specific handling requirements.
""".strip()


def _feedback_instructions(
    feedback: str | None,
) -> str:
    """Convert evaluator feedback into explicit revision instructions."""

    if not feedback:
        return (
            "This is the first generation attempt. "
            "Follow all generator rules."
        )

    instructions = [
        "Revise the previous approach to address this evaluator feedback:",
        feedback,
    ]

    feedback_lower = feedback.lower()

    if "readability" in feedback_lower:
        instructions.extend(
            [
                "",
                "READABILITY REVISION REQUIRED:",
                "- Use sentences of roughly 12 to 18 words.",
                "- Break long sentences into separate sentences.",
                "- Keep paragraphs to 1 to 3 sentences.",
                "- Prefer bullets for scope and requirements.",
                "- Remove filler and repeated explanations.",
                "- Use simple, direct business language.",
                "- Preserve compliance requirements while shortening prose.",
            ]
        )

    if "missing" in feedback_lower or "relevance" in feedback_lower:
        instructions.extend(
            [
                "",
                "RELEVANCE REVISION REQUIRED:",
                "- Address the missing RFP aspects directly.",
                "- Do not add unrelated capabilities.",
            ]
        )

    if "compliance" in feedback_lower or "violation" in feedback_lower:
        instructions.extend(
            [
                "",
                "COMPLIANCE REVISION REQUIRED:",
                "- Correct every listed violation.",
                "- Do not weaken or omit required business constraints.",
            ]
        )

    return "\n".join(instructions)


def _generate_section(
    department_id: str,
    guidance: str,
    metadata: dict,
    key_aspects: dict,
    feedback: str | None = None,
) -> str:
    """Generate one department proposal section."""

    currency = expected_currency(
        metadata.get("client_country")
    )

    feedback_instructions = _feedback_instructions(
        feedback
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
{feedback_instructions}

Draft this department's proposal section.

Keep the result concise.
Do not add facts that are absent from the structured inputs.
If a required commercial value is unknown, clearly mark it as pending
confirmation instead of inventing it.
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
    """Generate the Warehouse Operations section."""

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
    """Generate the Last Mile section."""

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
    """Generate the Reverse Logistics section."""

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
    """Generate one TrackFlow department proposal section."""

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
