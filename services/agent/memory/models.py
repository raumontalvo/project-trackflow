"""Typed models for TrackFlow agent memory and memory auditing."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc)


class MemoryType(str, Enum):
    """Memory categories explicitly allowed by TrackFlow."""

    CARRIER_RULE = "carrier_rule"
    RECURRING_INCIDENT = "recurring_incident"
    B2B_REPORT_PREFERENCE = "b2b_report_preference"


class MemoryDecision(str, Enum):
    """Explicit classification of a user's response to a proposal."""

    APPROVE = "approve"
    REJECT = "reject"
    EDIT = "edit"
    AMBIGUOUS = "ambiguous"
    UNRELATED = "unrelated"


class ProposalStatus(str, Enum):
    """Lifecycle state of a memory proposal."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"
    DISCARDED = "discarded"
    BLOCKED = "blocked"


class MemoryProposal(BaseModel):
    """Candidate memory proposed by the agent but not yet persisted."""

    proposal_id: str = Field(default_factory=lambda: str(uuid4()))
    conversation_id: str
    memory_type: MemoryType
    content: str

    country: Literal["US", "ES"] | None = None
    carrier: str | None = None
    b2b_client: str | None = None

    originating_message: str
    reason: str

    status: ProposalStatus = ProposalStatus.PENDING
    created_at: datetime = Field(default_factory=utc_now)


class MemoryDecisionResult(BaseModel):
    """Structured interpretation of the user's proposal decision."""

    decision: MemoryDecision
    edited_content: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    follow_up_question: str | None = None


class MemoryRecord(BaseModel):
    """Approved memory stored for reuse in future conversations."""

    memory_id: str = Field(default_factory=lambda: str(uuid4()))
    memory_type: MemoryType
    content: str

    country: Literal["US", "ES"] | None = None
    carrier: str | None = None
    b2b_client: str | None = None

    source_proposal_id: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime | None = None
    active: bool = True


class MemoryAuditRecord(BaseModel):
    """Immutable audit record for a proposal and the user's decision."""

    audit_id: str = Field(default_factory=lambda: str(uuid4()))
    proposal_id: str
    conversation_id: str

    proposed_memory: str
    originating_message: str

    outcome: ProposalStatus
    user_decision: MemoryDecision | None = None
    final_memory: str | None = None

    proposed_at: datetime
    resolved_at: datetime = Field(default_factory=utc_now)
