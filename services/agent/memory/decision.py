"""Explicit classification of user decisions for pending memory proposals."""

from __future__ import annotations

import json

from pydantic import BaseModel

from data.pipelines.rag import _openai_client, _required_env
from services.agent.memory.models import (
    MemoryDecision,
    MemoryDecisionResult,
    MemoryProposal,
)


class DecisionPayload(BaseModel):
    """Structured model output for proposal confirmation."""

    decision: MemoryDecision
    edited_content: str | None = None
    confidence: float
    follow_up_question: str | None = None


def classify_memory_decision(
    *,
    user_message: str,
    proposal: MemoryProposal,
) -> MemoryDecisionResult:
    """Classify a user's response against one specific pending proposal."""

    system_prompt = """
You classify a user's response to one pending TrackFlow memory proposal.

Allowed decisions:
- approve: the user clearly authorizes storing the proposal as written.
- reject: the user clearly says not to remember/store it.
- edit: the user wants it remembered but changes the proposed fact.
- unrelated: the user has moved to another topic instead of deciding.
- ambiguous: the response does not provide enough confidence to determine
  approve, reject, edit, or unrelated.

Rules:
- Never assume approval from silence, vagueness, politeness, or topic drift.
- "okay", "sure", or similar short replies count as approve only when they
  clearly refer to the pending memory request.
- If the user corrects the fact, use edit and return the corrected durable fact.
- If confidence is below 0.80, classify as ambiguous.
- If the same message both resolves the proposal AND asks a separate new
  question/request, copy only that separate request into follow_up_question.
- Do not put the approval/rejection/edit wording into follow_up_question.
- If there is no separate request, follow_up_question must be null.
- Return JSON only.

Exact output:
{
  "decision": "approve" | "reject" | "edit" | "ambiguous" | "unrelated",
  "edited_content": "corrected fact" | null,
  "confidence": 0.0,
  "follow_up_question": "separate new request from the same message" | null
}
""".strip()

    user_prompt = f"""
Pending proposal:
{proposal.content}

Original message that caused the proposal:
{proposal.originating_message}

User's current response:
{user_message}

Classify only the user's decision about this pending proposal.
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
        return MemoryDecisionResult(
            decision=MemoryDecision.AMBIGUOUS,
            edited_content=None,
            confidence=0.0,
            follow_up_question=None,
        )

    try:
        payload = DecisionPayload.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValueError):
        return MemoryDecisionResult(
            decision=MemoryDecision.AMBIGUOUS,
            edited_content=None,
            confidence=0.0,
            follow_up_question=None,
        )

    if payload.confidence < 0.80:
        return MemoryDecisionResult(
            decision=MemoryDecision.AMBIGUOUS,
            edited_content=None,
            confidence=payload.confidence,
            follow_up_question=None,
        )

    if (
        payload.decision == MemoryDecision.EDIT
        and not payload.edited_content
    ):
        return MemoryDecisionResult(
            decision=MemoryDecision.AMBIGUOUS,
            edited_content=None,
            confidence=payload.confidence,
            follow_up_question=None,
        )

    return MemoryDecisionResult(
        decision=payload.decision,
        edited_content=payload.edited_content,
        confidence=payload.confidence,
        follow_up_question=(
            payload.follow_up_question.strip()
            if payload.follow_up_question
            else None
        ),
    )
