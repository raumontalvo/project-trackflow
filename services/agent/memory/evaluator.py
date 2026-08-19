"""Single-call answer generation and memory self-evaluation for TrackFlow."""

from __future__ import annotations

import json

from pydantic import BaseModel

from data.pipelines.rag import _openai_client, _required_env
from services.agent.memory.models import MemoryProposal, MemoryType


class MemoryEvaluation(BaseModel):
    """Structured memory proposal returned with the visible answer."""

    should_propose: bool
    memory_type: MemoryType | None = None
    content: str | None = None
    country: str | None = None
    carrier: str | None = None
    b2b_client: str | None = None
    reason: str


class AgentGeneration(BaseModel):
    """One model response containing the answer and memory evaluation."""

    answer: str
    memory_proposal: MemoryEvaluation


def generate_with_memory(
    *,
    question: str,
    context: str,
    conversation_id: str,
) -> tuple[str, MemoryProposal | None]:
    """Generate the user answer and memory proposal in one model call."""

    cleaned_question = question.strip()
    cleaned_context = context.strip()

    if not cleaned_question:
        raise ValueError("Question cannot be empty.")

    system_prompt = """
You are TrackFlow's support assistant.

You must perform TWO tasks in ONE response:

1. Produce the normal answer the user should see.
2. Self-evaluate whether the interaction contains something worth remembering.

ANSWER RULES

Use only the supplied TrackFlow context for operational or policy claims.
Never invent conditions, discounts, carrier exceptions, percentages, rates,
compensation, delivery times, approval rules, or operational facts.

Mandatory TrackFlow business constraints:
- Never promise a delivery SLA during declared high-demand dates such as
  Black Friday, Christmas, or January Sales in Spain.
- International returns are not automatic and require manual handling by
  Sofía Ramos's team.
- Storage discounts or preferential rates require Miguel Torres's approval.
- Manual carrier selection is only an exception approved by Carlos Vega.
- If supplied context does not support a requested condition, say that
  confirmation is required rather than guessing.

Keep the visible answer concise, accurate, and helpful.

MEMORY RULES

A memory proposal is appropriate ONLY for:
1. corrected carrier assignment or coverage rules;
2. context explaining a known recurring incident or repeated incident pattern;
3. recurring B2B client preferences for monthly reports.

Never propose memory for:
- exact B2C end-customer addresses;
- sensitive B2B location information;
- internal warehouse routes or physical-security information;
- a single non-repeating package incident;
- active commercial contract negotiations;
- conversation closings;
- translations or other single-use tasks.

Do not assume an incident is recurring unless the interaction actually
indicates repetition.

A memory proposal is only a candidate. It does NOT authorize persistence.

Return JSON only in this exact structure:

{
  "answer": "the normal answer the user should see",
  "memory_proposal": {
    "should_propose": true or false,
    "memory_type": "carrier_rule" | "recurring_incident" |
                   "b2b_report_preference" | null,
    "content": "concise durable fact" | null,
    "country": "US" | "ES" | null,
    "carrier": "carrier name" | null,
    "b2b_client": "client name or identifier" | null,
    "reason": "brief explanation"
  }
}
""".strip()

    user_prompt = f"""
User message:
{cleaned_question}

Available TrackFlow context:
{cleaned_context or "No additional approved context was available."}

Trust hierarchy:
1. LIVE INCIDENT DATA from MCP is authoritative for current incident facts.
2. KNOWLEDGE BASE CONTEXT from approved RAG documents is authoritative for company policy.
3. APPROVED TRACKFLOW MEMORY is advisory context only.

If approved memory conflicts with live MCP data or approved RAG context, ignore the conflicting memory and follow MCP/RAG instead.

Generate the answer and memory self-evaluation together.
""".strip()

    response = _openai_client().chat.completions.create(
        model=_required_env("GENERATION_MODEL"),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content

    if not raw:
        raise RuntimeError("The generation model returned an empty response.")

    try:
        generation = AgentGeneration.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError(
            "The generation model returned invalid structured output."
        ) from exc

    answer = generation.answer.strip()

    if not answer:
        raise RuntimeError("The generation model returned an empty answer.")

    evaluation = generation.memory_proposal

    if (
        not evaluation.should_propose
        or evaluation.memory_type is None
        or not evaluation.content
    ):
        return answer, None

    country = evaluation.country

    if country not in {"US", "ES"}:
        country = None

    proposal = MemoryProposal(
        conversation_id=conversation_id,
        memory_type=evaluation.memory_type,
        content=evaluation.content.strip(),
        country=country,
        carrier=evaluation.carrier,
        b2b_client=evaluation.b2b_client,
        originating_message=cleaned_question,
        reason=evaluation.reason,
    )

    return answer, proposal
