"""Deterministic guardrails for the TrackFlow CX support agent."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo


GuardrailCategory = Literal[
    "allowed",
    "casual",
    "general_question",
    "personal_task",
    "security",
    "sensitive_data",
]

TrackFlowCountry = Literal["USA", "Spain"]

OutputFailureType = Literal[
    "structural",
    "content",
    "security",
]


@dataclass(frozen=True)
class GuardrailDecision:
    """Result of evaluating a user request before agent execution."""

    allowed: bool
    category: GuardrailCategory
    reason: str | None = None
    response: str | None = None


@dataclass(frozen=True)
class CountryPolicyDecision:
    """Result of enforcing the policy for the shipment's actual country."""

    allowed: bool
    shipment_country: TrackFlowCountry | None
    requested_country: TrackFlowCountry | None = None
    reason: str | None = None
    response: str | None = None


@dataclass(frozen=True)
class OutputGuardDecision:
    """Result of validating model output before returning it to the user."""

    allowed: bool
    failure_type: OutputFailureType | None = None
    reason: str | None = None
    safe_response: str | None = None


JAILBREAK_PATTERNS = (
    re.compile(
        r"\bignore\b.{0,40}\b(previous|prior|system|developer)\b"
        r".{0,40}\binstructions?\b",
        re.I,
    ),
    re.compile(
        r"\bforget\b.{0,40}\b(trackflow|instructions?|rules?)\b",
        re.I,
    ),
    re.compile(
        r"\bact as if\b.{0,40}\b(no|without)\b.{0,20}\brules?\b",
        re.I,
    ),
    re.compile(
        r"\bact as\b.{0,40}\b(no rules|unrestricted|unfiltered)\b",
        re.I,
    ),
    re.compile(
        r"\boverride\b.{0,40}\b(system|instructions?|rules?)\b",
        re.I,
    ),
    re.compile(
        r"\breveal\b.{0,40}\b(system prompt|hidden prompt|instructions?)\b",
        re.I,
    ),
    re.compile(
        r"\bshow\b.{0,40}\b(system prompt|hidden prompt|developer message)\b",
        re.I,
    ),
)


PERSONAL_TASK_TERMS = (
    "write me an essay",
    "write my essay",
    "do my homework",
    "help me with my homework",
    "write code for",
    "build me a website",
    "make me a website",
    "be my therapist",
    "act as my therapist",
    "relationship advice",
    "dating advice",
    "personal advice",
    "write my resume",
    "write me a resume",
    "make my resume",
)


SENSITIVE_DATA_PATTERNS = (
    re.compile(
        r"\b(carrier|ups|fedex|dhl|mrw|seur)\b"
        r".{0,30}\b(rate|rates|pricing|price|contract|terms)\b",
        re.I,
    ),
    re.compile(
        r"\b(negotiated|commercial)\b"
        r".{0,30}\b(rate|rates|terms|pricing)\b",
        re.I,
    ),
    re.compile(
        r"\b(exact|precise)\b"
        r".{0,20}\bwarehouse\b"
        r".{0,20}\b(location|address)\b",
        re.I,
    ),
    re.compile(
        r"\binternal\b"
        r".{0,20}\b(route|routes|warehouse location|warehouse address)\b",
        re.I,
    ),
)


CASUAL_PATTERNS = (
    re.compile(
        r"^\s*(hi|hello|hey|good morning|good afternoon|good evening)"
        r"[!.?\s]*$",
        re.I,
    ),
    re.compile(
        r"^\s*(thanks|thank you|thx)[!.?\s]*$",
        re.I,
    ),
    re.compile(
        r"^\s*how are you[?.!\s]*$",
        re.I,
    ),
)


GENERAL_LOGISTICS_TERMS = (
    "reverse logistics",
    "last mile delivery",
    "last-mile delivery",
    "what is logistics",
    "what is a return",
    "what is an sla",
)


GENERAL_QUESTION_PATTERNS = (
    re.compile(
        r"^\s*what time is it\b",
        re.I,
    ),
    re.compile(
        r"^\s*what(?:'s| is) the time\b",
        re.I,
    ),
    re.compile(
        r"^\s*what(?:'s| is) the capital of\b",
        re.I,
    ),
    re.compile(
        r"^\s*who (?:is|was)\b",
        re.I,
    ),
    re.compile(
        r"^\s*when (?:is|was|did)\b",
        re.I,
    ),
    re.compile(
        r"^\s*where (?:is|was)\b",
        re.I,
    ),
    re.compile(
        r"^\s*what (?:is|was|are|were)\b",
        re.I,
    ),
)


TRACKFLOW_DOMAIN_TERMS = (
    "trackflow",
    "shipment",
    "shipping",
    "tracking",
    "order",
    "parcel",
    "package",
    "return",
    "returns",
    "delivery",
    "incident",
    "ticket",
    "lost parcel",
    "failed delivery",
    "wrong address",
    "sla",
    "carrier",
    "logistics",
)


SPAIN_POLICY_PATTERN = re.compile(
    r"\b(spain|spanish|españa|spain's)\b.{0,30}\b"
    r"(policy|return|returns|sla)\b"
    r"|\b(policy|return|returns|sla)\b.{0,30}\b"
    r"(spain|spanish|españa|spain's)\b",
    re.I,
)

USA_POLICY_PATTERN = re.compile(
    r"\b(usa|u\.s\.|united states|american|us)\b.{0,30}\b"
    r"(policy|return|returns|sla)\b"
    r"|\b(policy|return|returns|sla)\b.{0,30}\b"
    r"(usa|u\.s\.|united states|american|us)\b",
    re.I,
)

LOS_ANGELES_PATTERN = re.compile(
    r"\b(los angeles|la)\b",
    re.I,
)

SPAIN_LOCATION_PATTERN = re.compile(
    r"\b(spain|españa|zaragoza|zgz)\b",
    re.I,
)


OUTPUT_INSTRUCTION_LEAK_PATTERNS = (
    re.compile(r"\bsystem prompt\b", re.I),
    re.compile(r"\bdeveloper (?:message|instructions?)\b", re.I),
    re.compile(r"\bhidden (?:prompt|instructions?)\b", re.I),
    re.compile(r"\binstruction hierarchy\b", re.I),
    re.compile(r"\binternal security rules?\b", re.I),
)


OUTPUT_SENSITIVE_DATA_PATTERNS = (
    re.compile(
        r"\b(?:ups|fedex|dhl|mrw|seur)\b.{0,40}"
        r"\bnegotiated (?:rate|rates|pricing|terms)\b",
        re.I,
    ),
    re.compile(
        r"\bnegotiated (?:rate|rates|pricing|terms)\b.{0,40}"
        r"\b(?:ups|fedex|dhl|mrw|seur)\b",
        re.I,
    ),
    re.compile(
        r"\bexact warehouse (?:location|address)\b",
        re.I,
    ),
    re.compile(
        r"\binternal physical rout(?:e|es|ing)\b",
        re.I,
    ),
)


SAFE_OUTPUT_FALLBACK = (
    "I can't provide that response because it may contain restricted "
    "TrackFlow information. I can still help with authorized shipment "
    "tracking, returns, SLAs, and delivery incidents."
)


TRACKFLOW_REDIRECT = (
    "My main role is TrackFlow logistics support, so I can help with "
    "shipment tracking, returns, SLAs, and delivery incidents."
)


def _is_trackflow_domain_question(lowered_question: str) -> bool:
    """Return True when the request clearly concerns TrackFlow's domain."""
    return any(
        term in lowered_question
        for term in TRACKFLOW_DOMAIN_TERMS
    )


def _brief_general_answer(question: str) -> str:
    """Return a brief supported general answer followed by TrackFlow redirect."""
    lowered = question.lower()

    if "time" in lowered and "tokyo" in lowered:
        tokyo_now = datetime.now(
            ZoneInfo("Asia/Tokyo")
        )

        current_time = tokyo_now.strftime("%I:%M %p").lstrip("0")

        return (
            f"The current time in Tokyo is {current_time}. "
            f"{TRACKFLOW_REDIRECT}"
        )

    if "capital" in lowered and "france" in lowered:
        return (
            f"The capital of France is Paris. "
            f"{TRACKFLOW_REDIRECT}"
        )

    return (
        "I can answer brief general questions, but I can't become a "
        f"general-purpose assistant. {TRACKFLOW_REDIRECT}"
    )


def evaluate_input(question: str) -> GuardrailDecision:
    """Apply deterministic scope, content, and anti-injection checks."""
    normalized = " ".join(question.strip().split())
    lowered = normalized.lower()

    for pattern in JAILBREAK_PATTERNS:
        if pattern.search(normalized):
            return GuardrailDecision(
                allowed=False,
                category="security",
                reason="prompt_injection",
                response=(
                    "I can't ignore, replace, reveal, or disable my TrackFlow "
                    "instructions. I can help with TrackFlow shipment tracking, "
                    "returns, SLAs, and delivery incidents."
                ),
            )

    for pattern in SENSITIVE_DATA_PATTERNS:
        if pattern.search(normalized):
            return GuardrailDecision(
                allowed=False,
                category="sensitive_data",
                reason="restricted_company_information",
                response=(
                    "I can't provide TrackFlow's confidential carrier rates, "
                    "commercial terms, exact warehouse locations, or internal "
                    "routing details. I can help with shipment tracking, returns, "
                    "SLAs, and delivery incidents."
                ),
            )

    if any(term in lowered for term in PERSONAL_TASK_TERMS):
        return GuardrailDecision(
            allowed=False,
            category="personal_task",
            reason="unrelated_personal_assistant_request",
            response=(
                "I can't act as a general-purpose personal assistant for that "
                "request. I'm TrackFlow's logistics support agent and can help "
                "with shipment tracking, returns, SLAs, and delivery incidents."
            ),
        )

    if any(pattern.search(normalized) for pattern in CASUAL_PATTERNS):
        return GuardrailDecision(
            allowed=False,
            category="casual",
            reason="casual_conversation",
            response=(
                "Hello! I'm here to help. My role is TrackFlow logistics support, "
                "so I can assist with shipment tracking, returns, SLAs, and "
                "delivery incidents."
            ),
        )

    if any(term in lowered for term in GENERAL_LOGISTICS_TERMS):
        return GuardrailDecision(
            allowed=False,
            category="casual",
            reason="general_logistics_question",
            response=(
                "Reverse logistics is the process of moving goods from the "
                "customer back toward the seller or logistics network for "
                "returns, repair, recycling, or disposal. For TrackFlow, I can "
                "help explain how that applies to a shipment, return, SLA, or "
                "delivery incident."
            ),
        )

    if (
        not _is_trackflow_domain_question(lowered)
        and any(
            pattern.search(normalized)
            for pattern in GENERAL_QUESTION_PATTERNS
        )
    ):
        return GuardrailDecision(
            allowed=False,
            category="general_question",
            reason="general_question_redirect",
            response=_brief_general_answer(normalized),
        )

    return GuardrailDecision(
        allowed=True,
        category="allowed",
    )


def detect_requested_policy_country(
    question: str,
) -> TrackFlowCountry | None:
    """Detect which country's policy the user is asking to apply."""
    if SPAIN_POLICY_PATTERN.search(question):
        return "Spain"

    if USA_POLICY_PATTERN.search(question):
        return "USA"

    return None


def infer_shipment_country_from_question(
    question: str,
) -> TrackFlowCountry | None:
    """Infer shipment country only from explicit TrackFlow location wording."""
    if LOS_ANGELES_PATTERN.search(question):
        return "USA"

    if SPAIN_LOCATION_PATTERN.search(question):
        return "Spain"

    return None


def enforce_country_policy(
    question: str,
    shipment_country: TrackFlowCountry | None,
) -> CountryPolicyDecision:
    """Prevent users from substituting another country's TrackFlow policy."""
    actual_country = shipment_country

    if actual_country is None:
        actual_country = infer_shipment_country_from_question(question)

    requested_country = detect_requested_policy_country(question)

    if (
        actual_country is not None
        and requested_country is not None
        and requested_country != actual_country
    ):
        return CountryPolicyDecision(
            allowed=False,
            shipment_country=actual_country,
            requested_country=requested_country,
            reason="country_policy_mismatch",
            response=(
                f"I can't apply TrackFlow's {requested_country} policy to a "
                f"shipment governed by the {actual_country} policy. "
                f"The {actual_country} return and SLA rules must be used for "
                "this shipment."
            ),
        )

    return CountryPolicyDecision(
        allowed=True,
        shipment_country=actual_country,
        requested_country=requested_country,
    )


def validate_output(answer: str | None) -> OutputGuardDecision:
    """Validate final agent output before it is returned to the user."""
    if answer is None or not isinstance(answer, str):
        return OutputGuardDecision(
            allowed=False,
            failure_type="structural",
            reason="missing_or_invalid_answer",
            safe_response=(
                "I couldn't produce a valid TrackFlow support response. "
                "Please try the request again."
            ),
        )

    normalized = " ".join(answer.strip().split())

    if not normalized:
        return OutputGuardDecision(
            allowed=False,
            failure_type="structural",
            reason="empty_answer",
            safe_response=(
                "I couldn't produce a valid TrackFlow support response. "
                "Please try the request again."
            ),
        )

    for pattern in OUTPUT_INSTRUCTION_LEAK_PATTERNS:
        if pattern.search(normalized):
            return OutputGuardDecision(
                allowed=False,
                failure_type="security",
                reason="internal_instruction_leak",
                safe_response=SAFE_OUTPUT_FALLBACK,
            )

    for pattern in OUTPUT_SENSITIVE_DATA_PATTERNS:
        if pattern.search(normalized):
            return OutputGuardDecision(
                allowed=False,
                failure_type="content",
                reason="sensitive_data_leak",
                safe_response=SAFE_OUTPUT_FALLBACK,
            )

    return OutputGuardDecision(
        allowed=True,
    )