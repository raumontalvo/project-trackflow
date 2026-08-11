"""Tests for TrackFlow WebSocket chat streaming."""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

import services.chat.manager as chat_manager_module
from services.api.main import app
from services.chat.manager import chat_manager


client = TestClient(app)


async def fake_stream_agent(
    question: str,
    session_id: str,
):
    """Fake streaming agent used to test WebSocket token delivery."""
    for token in ["Hello", " ", "there"]:
        await asyncio.sleep(0)

        yield {
            "type": "token",
            "token": token,
        }

    yield {
        "type": "completed",
        "run_id": "run_test",
        "state": {
            "question": question,
            "answer": "Hello there",
        },
    }


async def redirect_stream_agent(
    question: str,
    session_id: str,
):
    """
    Stream recognizable tokens so the test can prove cancellation.

    The first turn emits OLD-* tokens.
    The redirected turn emits RETURN-* tokens.
    """
    if "return" in question.lower():
        tokens = [
            "RETURN-1",
            "RETURN-2",
        ]
    else:
        tokens = [
            "OLD-1",
            "OLD-2",
            "OLD-3",
            "OLD-4",
        ]

    for token in tokens:
        await asyncio.sleep(0.05)

        yield {
            "type": "token",
            "token": token,
        }

    yield {
        "type": "completed",
        "run_id": "run_redirect",
        "state": {
            "question": question,
            "answer": "".join(tokens),
        },
    }


def receive_initial_events(
    websocket,
    session_id: str,
):
    """Receive and validate connection and rehydration events."""
    connected = websocket.receive_json()

    assert connected["event"] == "session_connected"
    assert connected["data"]["session_id"] == session_id
    assert connected["data"]["agent_id"] == "first_line_cx"

    history = websocket.receive_json()

    assert history["event"] == "session_history"
    assert history["data"]["session_id"] == session_id

    return connected, history


def test_websocket_streams_token_chunks(
    monkeypatch,
):
    """A user message should stream chunks and then complete."""
    monkeypatch.setattr(
        chat_manager_module,
        "stream_agent",
        fake_stream_agent,
    )

    session_id = "chat_test_stream"

    with client.websocket_connect(
        (
            f"/ws/chat/{session_id}"
            "?user_id=user_1"
            "&client_id=client_1"
        )
    ) as websocket:
        _, history = receive_initial_events(
            websocket,
            session_id,
        )

        assert history["data"]["messages"] == []

        websocket.send_json(
            {
                "event": "user_message",
                "data": {
                    "session_id": session_id,
                    "input": "Where is my parcel?",
                },
            }
        )

        first = websocket.receive_json()
        second = websocket.receive_json()
        third = websocket.receive_json()
        completed = websocket.receive_json()

        assert first == {
            "event": "token_chunk",
            "data": {
                "session_id": session_id,
                "token": "Hello",
                "sequence": 0,
            },
        }

        assert second["event"] == "token_chunk"
        assert second["data"]["token"] == " "
        assert second["data"]["sequence"] == 1

        assert third["event"] == "token_chunk"
        assert third["data"]["token"] == "there"
        assert third["data"]["sequence"] == 2

        assert completed["event"] == "generation_completed"
        assert completed["data"]["session_id"] == session_id
        assert completed["data"]["message_id"].startswith("msg_")


def test_interrupt_aborts_generation_and_redirects(
    monkeypatch,
):
    """
    Interrupt must stop the old generation and start a redirected turn.
    """
    monkeypatch.setattr(
        chat_manager_module,
        "stream_agent",
        redirect_stream_agent,
    )

    session_id = "chat_test_interrupt"

    with client.websocket_connect(
        (
            f"/ws/chat/{session_id}"
            "?user_id=user_2"
            "&client_id=client_2"
        )
    ) as websocket:
        receive_initial_events(
            websocket,
            session_id,
        )

        websocket.send_json(
            {
                "event": "user_message",
                "data": {
                    "session_id": session_id,
                    "input": "Track my order",
                },
            }
        )

        first_chunk = websocket.receive_json()

        assert first_chunk["event"] == "token_chunk"
        assert first_chunk["data"]["token"] == "OLD-1"

        websocket.send_json(
            {
                "event": "interrupt_requested",
                "data": {
                    "session_id": session_id,
                    "new_input": (
                        "Wait, I want to make a return"
                    ),
                },
            }
        )

        interrupted = websocket.receive_json()

        assert interrupted["event"] == "generation_interrupted"
        assert interrupted["data"]["session_id"] == session_id
        assert interrupted["data"]["status"] == "interrupted"
        assert interrupted["data"]["message_id"].startswith("msg_")

        redirected_tokens: list[str] = []

        while True:
            event = websocket.receive_json()

            if event["event"] == "token_chunk":
                redirected_tokens.append(
                    event["data"]["token"]
                )

                assert not event["data"]["token"].startswith(
                    "OLD-"
                )

            if event["event"] == "generation_completed":
                break

        assert redirected_tokens == [
            "RETURN-1",
            "RETURN-2",
        ]


def test_reconnect_rehydrates_same_chat_session(
    monkeypatch,
):
    """
    Reconnect with the same session_id restores full conversation history.
    """
    monkeypatch.setattr(
        chat_manager_module,
        "stream_agent",
        fake_stream_agent,
    )

    session_id = "chat_test_reconnect"

    with client.websocket_connect(
        (
            f"/ws/chat/{session_id}"
            "?user_id=user_3"
            "&client_id=client_3"
        )
    ) as websocket:
        _, initial_history = receive_initial_events(
            websocket,
            session_id,
        )

        assert initial_history["data"]["messages"] == []

        websocket.send_json(
            {
                "event": "user_message",
                "data": {
                    "session_id": session_id,
                    "input": "Where is my parcel?",
                },
            }
        )

        streamed_content = ""

        while True:
            event = websocket.receive_json()

            if event["event"] == "token_chunk":
                streamed_content += event["data"]["token"]

            if event["event"] == "generation_completed":
                break

        assert streamed_content == "Hello there"

    first_session = chat_manager.get_session(
        session_id
    )

    assert first_session is not None

    with client.websocket_connect(
        (
            f"/ws/chat/{session_id}"
            "?user_id=user_3"
            "&client_id=client_3"
        )
    ) as websocket:
        connected, history = receive_initial_events(
            websocket,
            session_id,
        )

        assert connected["data"]["session_id"] == session_id

        messages = history["data"]["messages"]

        assert len(messages) == 2

        assert messages[0]["role"] == "user"
        assert (
            messages[0]["content"]
            == "Where is my parcel?"
        )
        assert messages[0]["status"] == "completed"
        assert messages[0]["message_id"].startswith(
            "msg_"
        )

        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"] == "Hello there"
        assert messages[1]["status"] == "completed"
        assert messages[1]["message_id"].startswith(
            "msg_"
        )

    second_session = chat_manager.get_session(
        session_id
    )

    assert second_session is first_session
    assert second_session.agent_id == "first_line_cx"
    assert second_session.user_id == "user_3"
    assert second_session.client_id == "client_3"