"""Classifier node for the TrackFlow RFP intake workflow."""

from __future__ import annotations

import json
import re

from pydantic import ValidationError

from data.pipelines.rfp_intake.llm import (
    generation_model,
    openai_client,
)
from data.pipelines.rfp_intake.state import RFPIntakeState
from services.api.schemas import ClassificationResult


SYSTEM_PROMPT = """
You are the intake classifier for TrackFlow, a logistics company.

Your only job is to decide whether an uploaded document is a legitimate
inbound request from a prospective client asking TrackFlow to provide a
logistics proposal.

TrackFlow provides:
- warehousing
- last-mile shipping and carrier management
- returns / reverse logistics

ACCEPT the document when:
- a prospective client asks TrackFlow for a proposal, quote, or logistics
  partnership involving one or more TrackFlow services;
- the request can be formal or informal;
- the document does NOT need to use the words "RFP" or
  "Request for Proposal";
- an email-style request can still be a legitimate RFP.

REJECT the document when:
- a carrier, supplier, software vendor, or other company is trying to sell
  its own services to TrackFlow;
- it is a partnership solicitation directed at TrackFlow;
- it is marketing material;
- it is not asking TrackFlow to provide logistics services;
- it contains logistics terminology or shipment volumes but those describe
  the sender's commercial offer rather than a client's logistics need.

Important:
Determine who is asking whom to provide services.
Do not classify based only on keywords such as "RFP", "proposal",
"shipping", "rates", or volume numbers.

Return ONLY valid JSON using this exact structure:

{
  "is_rfp": true,
  "confidence": 0.0,
  "reason": "short explanation"
}

Rules:
- is_rfp must be true or false.
- confidence must be between 0.0 and 1.0.
- reason must be concise and based only on evidence in the document.
- Do not return Markdown.
- Do not return code fences.
- Do not extract RFP metadata in this step.
""".strip()


def _extract_json(text: str) -> dict:
    """
    Parse a JSON object from the model response.

    Handles both clean JSON and accidental Markdown code fences.
    """

    cleaned = text.strip()

    if cleaned.startswith("```"):
        cleaned = re.sub(
            r"^```(?:json)?\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)

        if not match:
            raise ValueError(
                "Classifier model did not return a JSON object."
            )

        return json.loads(match.group(0))


def classify_markdown(markdown: str) -> ClassificationResult:
    """
    Classify converted Markdown as a valid or invalid TrackFlow RFP.
    """

    document = markdown.strip()

    if not document:
        raise ValueError("Cannot classify an empty document.")

    user_prompt = f"""
Determine whether the following document is a legitimate inbound TrackFlow
RFP according to the classification rules.

DOCUMENT:
----------------
{document}
----------------

Return only the required JSON object.
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
    )

    content = response.choices[0].message.content

    if not content:
        raise RuntimeError(
            "The classifier model returned an empty response."
        )

    raw_result = _extract_json(content)

    try:
        return ClassificationResult.model_validate(raw_result)
    except ValidationError as exc:
        raise ValueError(
            "Classifier returned invalid structured data."
        ) from exc


def classify_rfp_node(
    state: RFPIntakeState,
) -> RFPIntakeState:
    """
    LangGraph node that classifies the converted RFP document.
    """

    markdown = state.get("markdown", "").strip()

    result = classify_markdown(markdown)

    return {
        "classification": result.model_dump(mode="json"),
        "is_rfp": result.is_rfp,
        "rejection_reason": (
            None if result.is_rfp else result.reason
        ),
    }


def route_after_classification(
    state: RFPIntakeState,
) -> str:
    """
    Route valid RFPs onward and rejected documents to discard handling.
    """

    if state.get("is_rfp"):
        return "valid"

    return "discarded"