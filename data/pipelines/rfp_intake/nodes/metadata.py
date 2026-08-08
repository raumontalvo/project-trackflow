"""Metadata extraction and deterministic routing for TrackFlow RFP intake."""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from data.pipelines.rfp_intake.config import (
    COUNTRY_TO_CURRENCY,
    SERVICE_TO_DEPARTMENT,
)
from data.pipelines.rfp_intake.llm import generation_model, openai_client
from data.pipelines.rfp_intake.state import RFPIntakeState


ServiceId = Literal[
    "warehousing",
    "last_mile",
    "returns",
]

ClientCountry = Literal[
    "US",
    "Spain",
]


class ExtractedRFPMetadata(BaseModel):
    """Structured metadata extracted only from a valid TrackFlow RFP."""

    client_name: str | None = None
    client_country: ClientCountry | None = None

    services_requested: list[ServiceId] = Field(
        default_factory=list
    )

    monthly_volume: int | None = Field(
        default=None,
        ge=0,
    )

    deadline: date | None = None
    budget_range: str | None = None


SYSTEM_PROMPT = """
You extract trusted business metadata from legitimate TrackFlow RFPs.

TrackFlow supports exactly these service identifiers:

- warehousing
- last_mile
- returns

Return ONLY valid JSON with this exact structure:

{
  "client_name": null,
  "client_country": null,
  "services_requested": [],
  "monthly_volume": null,
  "deadline": null,
  "budget_range": null
}

Rules:

CLIENT NAME
- Extract the prospective client's organization name.
- Do not use a vendor, carrier, or TrackFlow as the client.

CLIENT COUNTRY
- Allowed values are exactly "US", "Spain", or null.
- Use the client's country of origin when explicitly supported.
- Los Angeles, California, USA means "US".
- A Spanish organization explicitly described as Spanish means "Spain".
- Do not guess from a company name alone.

SERVICES
- warehousing = storage, fulfillment storage, warehouse operations.
- last_mile = shipping fulfillment, delivery, carrier selection, or carrier
  management requested from TrackFlow.
- returns = returns handling, reverse logistics, inspection,
  reconditioning, or restocking returned goods.
- Only include services the client actually requests.
- Explicit exclusions override general logistics language.
- If the client says it uses its own carrier and does not need last-mile
  management, do NOT include "last_mile".

MONTHLY VOLUME
- Extract only a quantity explicitly describing orders or shipments per month.
- Do NOT treat SKU count, pallet count, inventory count, carrier pricing
  thresholds, or annual volume as monthly order volume.
- Example: "5,000 orders a month" → 5000.
- Example: "15,000 SKUs" → null.

DEADLINE
- Extract only a proposal submission / response deadline.
- Use ISO format YYYY-MM-DD.
- Do NOT treat an implementation date, desired go-live date, onboarding date,
  or service start date as the proposal deadline.
- If no proposal deadline is given, return null.

BUDGET
- Extract a reference budget only if explicitly stated.
- Otherwise return null.

Never invent missing information.
Do not return Markdown or code fences.
""".strip()


def _extract_json(text: str) -> dict:
    """Parse a JSON object from a model response."""

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
        match = re.search(
            r"\{.*\}",
            cleaned,
            flags=re.DOTALL,
        )

        if not match:
            raise ValueError(
                "Metadata model did not return a JSON object."
            )

        return json.loads(match.group(0))


def extract_rfp_metadata(
    markdown: str,
) -> ExtractedRFPMetadata:
    """Extract trusted metadata from an accepted TrackFlow RFP."""

    document = markdown.strip()

    if not document:
        raise ValueError(
            "Cannot extract metadata from an empty document."
        )

    user_prompt = f"""
Extract the TrackFlow RFP metadata from this accepted client document.

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
            "The metadata model returned an empty response."
        )

    raw_result = _extract_json(content)

    try:
        return ExtractedRFPMetadata.model_validate(
            raw_result
        )
    except ValidationError as exc:
        raise ValueError(
            "Metadata model returned invalid structured data."
        ) from exc


def resolve_departments(
    services_requested: list[str],
) -> list[str]:
    """
    Map controlled service IDs to TrackFlow department IDs.

    Department routing is deterministic and never delegated to the LLM.
    """

    departments: list[str] = []

    for service in services_requested:
        department = SERVICE_TO_DEPARTMENT.get(service)

        if department and department not in departments:
            departments.append(department)

    return departments


def currency_for_country(
    country: str | None,
) -> str | None:
    """Resolve TrackFlow proposal currency from client country."""

    if country is None:
        return None

    return COUNTRY_TO_CURRENCY.get(country)


def extract_metadata_node(
    state: RFPIntakeState,
) -> RFPIntakeState:
    """LangGraph node for metadata extraction and department routing."""

    if not state.get("is_rfp"):
        raise ValueError(
            "Metadata extraction cannot run on a rejected document."
        )

    markdown = state.get("markdown", "").strip()

    result = extract_rfp_metadata(markdown)

    departments = resolve_departments(
        result.services_requested
    )

    metadata = result.model_dump(mode="json")

    metadata["departments_needed"] = departments
    metadata["currency"] = currency_for_country(
        result.client_country
    )

    return {
        "rfp_metadata": metadata,
        "active_departments": departments,
    }