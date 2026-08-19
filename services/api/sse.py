"""Server-Sent Events support for TrackFlow real-time notifications."""

from __future__ import annotations

import asyncio
import json
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


RFP_TICKET_CREATED = "rfp_ticket_created"
REPLAY_LIMIT = 100


@dataclass(frozen=True)
class SSEEvent:
    """One TrackFlow server-sent event."""

    event_id: int
    event: str
    data: dict[str, Any]

    def encode(self) -> str:
        """Encode the event using standard SSE wire format."""

        payload = json.dumps(
            self.data,
            separators=(",", ":"),
            default=str,
        )

        return (
            f"id: {self.event_id}\n"
            f"event: {self.event}\n"
            f"data: {payload}\n\n"
        )


@dataclass(frozen=True)
class Subscriber:
    """One independently connected SSE client."""

    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue[SSEEvent]


class SSEBroker:
    """
    Fan out events to independent clients and keep a short replay buffer.

    Publishing may occur from a FastAPI background worker thread, so delivery
    is scheduled safely onto each subscriber's event loop.
    """

    def __init__(self) -> None:
        self._subscribers: set[Subscriber] = set()
        self._history: deque[SSEEvent] = deque(
            maxlen=REPLAY_LIMIT
        )
        self._next_event_id = 1
        self._lock = threading.Lock()

    def subscribe(
        self,
        last_event_id: int | None = None,
    ) -> Subscriber:
        subscriber = Subscriber(
            loop=asyncio.get_running_loop(),
            queue=asyncio.Queue(),
        )

        with self._lock:
            self._subscribers.add(subscriber)

            replay = [
                event
                for event in self._history
                if (
                    last_event_id is not None
                    and event.event_id > last_event_id
                )
            ]

        for event in replay:
            subscriber.queue.put_nowait(event)

        return subscriber

    def unsubscribe(
        self,
        subscriber: Subscriber,
    ) -> None:
        with self._lock:
            self._subscribers.discard(subscriber)

    def publish(
        self,
        *,
        event: str,
        data: dict[str, Any],
    ) -> SSEEvent:
        with self._lock:
            sse_event = SSEEvent(
                event_id=self._next_event_id,
                event=event,
                data=data,
            )

            self._next_event_id += 1
            self._history.append(sse_event)

            subscribers = tuple(self._subscribers)

        for subscriber in subscribers:
            subscriber.loop.call_soon_threadsafe(
                subscriber.queue.put_nowait,
                sse_event,
            )

        return sse_event


broker = SSEBroker()


def publish_rfp_ticket_created(
    *,
    ticket_id: str,
    rfp_id: str,
    client_name: str | None,
    client_country: str | None,
    services_requested: list[str],
    created_at: datetime | None = None,
) -> SSEEvent:
    """Publish the required TrackFlow new-RFP notification."""

    timestamp = created_at or datetime.now(timezone.utc)

    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    return broker.publish(
        event=RFP_TICKET_CREATED,
        data={
            "ticket_id": ticket_id,
            "rfp_id": rfp_id,
            "client_name": client_name,
            "client_country": client_country,
            "services_requested": services_requested,
            "status": "analyzing",
            "created_at": timestamp.isoformat().replace(
                "+00:00",
                "Z",
            ),
        },
    )
