"""TrackFlow-specific memory policy validation."""

from __future__ import annotations

import re
from dataclasses import dataclass

from services.agent.memory.models import MemoryProposal, MemoryType


@dataclass
class PolicyResult:
    """Result returned by TrackFlow memory policy validation."""

    allowed: bool
    reason: str


ADDRESS_PATTERN = re.compile(
    r"\b\d{1,6}\s+[A-Za-z0-9.'\- ]+\s"
    r"(?:street|st|avenue|ave|road|rd|boulevard|blvd|lane|ln|drive|dr|court|ct)\b",
    re.IGNORECASE,
)

WAREHOUSE_ROUTE_TERMS = (
    "warehouse route",
    "internal route",
    "internal warehouse",
    "warehouse access",
    "loading route",
    "dock route",
)

COMMERCIAL_NEGOTIATION_TERMS = (
    "contract negotiation",
    "commercial negotiation",
    "pricing negotiation",
    "negotiating contract",
    "active contract",
    "deal terms",
)


def contains_sensitive_location_data(text: str) -> bool:
    """Detect exact addresses or sensitive warehouse-route information."""
    normalized = text.strip().lower()

    if ADDRESS_PATTERN.search(text):
        return True

    return any(term in normalized for term in WAREHOUSE_ROUTE_TERMS)


def contains_active_commercial_negotiation(text: str) -> bool:
    """Detect information belonging to active commercial negotiations."""
    normalized = text.strip().lower()
    return any(term in normalized for term in COMMERCIAL_NEGOTIATION_TERMS)


def validate_memory_proposal(proposal: MemoryProposal) -> PolicyResult:
    """Validate a proposed memory against TrackFlow's company constraints."""

    content = proposal.content.strip()

    if not content:
        return PolicyResult(
            allowed=False,
            reason="Empty memory proposals cannot be stored.",
        )

    if contains_sensitive_location_data(content):
        return PolicyResult(
            allowed=False,
            reason=(
                "TrackFlow forbids storing exact customer addresses or "
                "sensitive internal warehouse-route information for both "
                "B2B and B2C contexts."
            ),
        )

    if contains_active_commercial_negotiation(content):
        return PolicyResult(
            allowed=False,
            reason=(
                "Active commercial contract negotiation data belongs in the CRM "
                "and must never enter support-agent memory."
            ),
        )

    if proposal.memory_type not in {
        MemoryType.CARRIER_RULE,
        MemoryType.RECURRING_INCIDENT,
        MemoryType.B2B_REPORT_PREFERENCE,
    }:
        return PolicyResult(
            allowed=False,
            reason="The proposal does not match an approved TrackFlow memory category.",
        )

    if (
        proposal.memory_type == MemoryType.RECURRING_INCIDENT
        and "recurr" not in proposal.reason.lower()
        and "multiple" not in proposal.reason.lower()
        and "repeat" not in proposal.reason.lower()
        and "third" not in proposal.reason.lower()
    ):
        return PolicyResult(
            allowed=False,
            reason=(
                "A single non-repeating package incident is not memorable. "
                "Recurring incident context must show evidence of repetition."
            ),
        )

    return PolicyResult(
        allowed=True,
        reason="Proposal satisfies TrackFlow memory policy.",
    )
