"""WebSocket chat route for the TrackFlow First-line CX agent."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services.chat.manager import chat_manager


router = APIRouter(tags=["chat"])


@router.websocket("/ws/chat/{session_id}")
async def chat_websocket(
    websocket: WebSocket,
    session_id: str,
) -> None:
    """
    Bidirectional WebSocket for TrackFlow CX chat streaming.

    Query parameters:
        user_id: client user identifier
        client_id: TrackFlow client identifier

    Client events:
        user_message
        interrupt_requested

    Server events:
        session_connected
        session_history
        token_chunk
        generation_interrupted
        generation_completed
        generation_error
        chat_error
    """
    user_id = websocket.query_params.get("user_id", "").strip()
    client_id = websocket.query_params.get("client_id", "").strip()

    if not user_id or not client_id:
        await websocket.close(
            code=1008,
            reason="user_id and client_id are required.",
        )
        return

    try:
        session = await chat_manager.get_or_create_session(
            session_id=session_id,
            user_id=user_id,
            client_id=client_id,
        )
    except ValueError as exc:
        await websocket.close(
            code=1008,
            reason=str(exc),
        )
        return

    await websocket.accept()

    subscriber = await chat_manager.subscribe(session_id)

    async def send_session_events() -> None:
        """Forward published session events to this WebSocket."""
        while True:
            event = await subscriber.get()
            await websocket.send_json(event)

    sender_task = asyncio.create_task(
        send_session_events()
    )

    try:
        await websocket.send_json(
            {
                "event": "session_connected",
                "data": {
                    "session_id": session.session_id,
                    "agent_id": session.agent_id,
                    "user_id": session.user_id,
                    "client_id": session.client_id,
                    "status": session.status,
                },
            }
        )

        history = chat_manager.get_messages(session_id)

        await websocket.send_json(
            {
                "event": "session_history",
                "data": {
                    "session_id": session_id,
                    "messages": [
                        {
                            "message_id": message.message_id,
                            "role": message.role,
                            "content": message.content,
                            "status": message.status,
                        }
                        for message in history
                    ],
                },
            }
        )

        while True:
            payload = await websocket.receive_json()

            event_name = payload.get("event")
            data = payload.get("data")

            if not isinstance(data, dict):
                await websocket.send_json(
                    {
                        "event": "chat_error",
                        "data": {
                            "session_id": session_id,
                            "error": "Event data must be an object.",
                        },
                    }
                )
                continue

            incoming_session_id = str(
                data.get("session_id", "")
            ).strip()

            if incoming_session_id != session_id:
                await websocket.send_json(
                    {
                        "event": "chat_error",
                        "data": {
                            "session_id": session_id,
                            "error": (
                                "Event session_id does not match "
                                "the WebSocket session."
                            ),
                        },
                    }
                )
                continue

            if event_name == "user_message":
                question = str(
                    data.get("input", "")
                ).strip()

                if not question:
                    await websocket.send_json(
                        {
                            "event": "chat_error",
                            "data": {
                                "session_id": session_id,
                                "error": "input cannot be empty.",
                            },
                        }
                    )
                    continue

                try:
                    await chat_manager.start_generation(
                        session_id=session_id,
                        question=question,
                    )
                except (ValueError, RuntimeError) as exc:
                    await websocket.send_json(
                        {
                            "event": "chat_error",
                            "data": {
                                "session_id": session_id,
                                "error": str(exc),
                            },
                        }
                    )

            elif event_name == "interrupt_requested":
                new_input = str(
                    data.get("new_input", "")
                ).strip()

                if not new_input:
                    await websocket.send_json(
                        {
                            "event": "chat_error",
                            "data": {
                                "session_id": session_id,
                                "error": "new_input cannot be empty.",
                            },
                        }
                    )
                    continue

                try:
                    await chat_manager.interrupt_and_redirect(
                        session_id=session_id,
                        new_input=new_input,
                    )
                except (ValueError, RuntimeError) as exc:
                    await websocket.send_json(
                        {
                            "event": "chat_error",
                            "data": {
                                "session_id": session_id,
                                "error": str(exc),
                            },
                        }
                    )

            else:
                await websocket.send_json(
                    {
                        "event": "chat_error",
                        "data": {
                            "session_id": session_id,
                            "error": (
                                f"Unsupported event: {event_name}"
                            ),
                        },
                    }
                )

    except WebSocketDisconnect:
        pass

    finally:
        sender_task.cancel()

        try:
            await sender_task
        except asyncio.CancelledError:
            pass

        await chat_manager.unsubscribe(
            session_id,
            subscriber,
        )