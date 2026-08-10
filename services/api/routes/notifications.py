"""Authenticated Server-Sent Events endpoint for TrackFlow notifications."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from services.api.auth import get_current_user
from services.api.sse import broker


router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
)


@router.get("/stream")
async def notification_stream(
    request: Request,
    _current_user=Depends(get_current_user),
) -> StreamingResponse:
    """
    Stream TrackFlow notifications to one authenticated dashboard connection.

    Each client gets an independent broker queue. Keep-alive comments are sent
    periodically so proxies and browsers can detect broken connections.
    """

    last_event_id_header = request.headers.get(
        "Last-Event-ID"
    )

    last_event_id: int | None = None

    if last_event_id_header:
        try:
            last_event_id = int(last_event_id_header)
        except ValueError:
            last_event_id = None

    subscriber = broker.subscribe(
        last_event_id=last_event_id
    )
    queue = subscriber.queue

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break

                try:
                    event = await asyncio.wait_for(
                        queue.get(),
                        timeout=15.0,
                    )

                    yield event.encode()

                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"

        finally:
            broker.unsubscribe(subscriber)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
