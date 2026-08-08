"""Sales-facing synthesizer for TrackFlow RFP intake."""

from __future__ import annotations

import json

from data.pipelines.rfp_intake.llm import generation_model, openai_client
from data.pipelines.rfp_intake.state import RFPIntakeState


SYSTEM_PROMPT = """
You are the final TrackFlow RFP intake synthesizer.

The department workers have already analyzed the RFP.

Your job is NOT to redo their work and NOT to invent information.

Identify the unresolved questions Sales should clarify before proposal
generation.

Return ONLY:

{
  "sales_questions": []
}

Rules:
- Only use information present in metadata and worker results.
- Prioritize missing information that could affect scope, capacity,
  pricing, timing, or implementation.
- Do not invent answers.
- Do not generate pricing.
- Do not promise SLAs.
- Keep questions concise and actionable.
""".strip()


def synthesize_sales_questions(
    metadata: dict,
    department_results: dict[str, dict],
) -> list[str]:
    """Generate a consolidated set of Sales follow-up questions."""

    user_prompt = f"""
RFP METADATA:
{json.dumps(metadata, ensure_ascii=False)}

DEPARTMENT RESULTS:
{json.dumps(department_results, ensure_ascii=False)}

Return the consolidated Sales questions.
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
            "The intake synthesizer returned an empty response."
        )

    raw = json.loads(content)

    questions = raw.get("sales_questions", [])

    if not isinstance(questions, list):
        return []

    return [
        str(question).strip()
        for question in questions
        if str(question).strip()
    ]


def synthesizer_node(
    state: RFPIntakeState,
) -> RFPIntakeState:
    """Build the final Sales-facing intake summary."""

    metadata = state.get("rfp_metadata", {})
    department_results = state.get(
        "department_results",
        {},
    )

    sales_questions = synthesize_sales_questions(
        metadata=metadata,
        department_results=department_results,
    )

    summary = {
        "client_name": metadata.get("client_name"),
        "client_country": metadata.get("client_country"),
        "currency": metadata.get("currency"),
        "departments_needed": state.get(
            "active_departments",
            [],
        ),
        "department_results": list(
            department_results.values()
        ),
        "sales_questions": sales_questions,
    }

    return {
        "summary": summary,
    }