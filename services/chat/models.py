"""Chat session models for TrackFlow WebSocket communication."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


ChatStatus = Literal["active", "interrupted", "closed"]


class ChatSession(BaseModel):
    """TrackFlow chat session required by the Part 2 CONTEXT."""

    session_id: str = Field(..., min_length=1)
    agent_id: Literal["first_line_cx"] = "first_line_cx"
    user_id: str = Field(..., min_length=1)
    client_id: str = Field(..., min_length=1)
    status: ChatStatus = "active"
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class TokenChunkData(BaseModel):
    """Payload for a streamed token event."""

    session_id: str
    token: str
    sequence: int


class InterruptRequestedData(BaseModel):
    """Payload sent by the client to interrupt active generation."""

    session_id: str
    new_input: str = Field(..., min_length=1)


class GenerationInterruptedData(BaseModel):
    """Payload broadcast after an active generation is aborted."""

    session_id: str
    message_id: str
    status: Literal["interrupted"] = "interrupted"


class GenerationCompletedData(BaseModel):
    """Payload broadcast after generation finishes normally."""

    session_id: str
    message_id: str


class ChatMessageData(BaseModel):
    """Client message used to start a new agent generation."""

    session_id: str
    input: str = Field(..., min_length=1)


class WebSocketEvent(BaseModel):
    """Generic structured event sent over the WebSocket."""

    event: str
    data: dict