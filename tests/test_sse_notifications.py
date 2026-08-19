"""Tests for TrackFlow SSE notifications."""

from __future__ import annotations

import asyncio
import json

from services.api.sse import (
    RFP_TICKET_CREATED,
    SSEBroker,
    SSEEvent,
)


def test_sse_wire_format_contains_id_event_and_json() -> None:
    event = SSEEvent(
        event_id=42,
        event=RFP_TICKET_CREATED,
        data={
            "ticket_id": "tkt_0225",
            "status": "analyzing",
        },
    )

    encoded = event.encode()

    assert encoded.startswith(
        "id: 42\nevent: rfp_ticket_created\n"
    )
    assert encoded.endswith("\n\n")

    data_line = next(
        line
        for line in encoded.splitlines()
        if line.startswith("data: ")
    )

    payload = json.loads(
        data_line.removeprefix("data: ")
    )

    assert payload["ticket_id"] == "tkt_0225"
    assert payload["status"] == "analyzing"


def test_all_subscribers_receive_independent_event() -> None:
    async def scenario() -> None:
        broker = SSEBroker()

        first = broker.subscribe()
        second = broker.subscribe()

        published = broker.publish(
            event=RFP_TICKET_CREATED,
            data={"ticket_id": "tkt_1"},
        )

        first_event = await asyncio.wait_for(
            first.queue.get(),
            timeout=1,
        )

        second_event = await asyncio.wait_for(
            second.queue.get(),
            timeout=1,
        )

        assert first_event == published
        assert second_event == published

    asyncio.run(scenario())


def test_reconnect_replays_events_after_last_event_id() -> None:
    async def scenario() -> None:
        broker = SSEBroker()

        first = broker.publish(
            event=RFP_TICKET_CREATED,
            data={"ticket_id": "tkt_1"},
        )

        second = broker.publish(
            event=RFP_TICKET_CREATED,
            data={"ticket_id": "tkt_2"},
        )

        subscriber = broker.subscribe(
            last_event_id=first.event_id
        )

        replayed = await asyncio.wait_for(
            subscriber.queue.get(),
            timeout=1,
        )

        assert replayed == second
        assert subscriber.queue.empty()

    asyncio.run(scenario())
