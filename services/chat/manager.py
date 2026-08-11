"""In-memory chat session, pub/sub, and generation management."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Literal
from uuid import uuid4

from services.agent.graph import stream_agent
from services.chat.models import ChatSession


MessageRole = Literal["user", "assistant"]
MessageStatus = Literal[
    "completed",
    "streaming",
    "interrupted",
    "error",
]


@dataclass
class ChatMessage:
    """One persisted message in a TrackFlow chat session."""

    message_id: str
    session_id: str
    role: MessageRole
    content: str
    status: MessageStatus


@dataclass
class ActiveGeneration:
    """One running generation for a chat session."""

    message_id: str
    task: asyncio.Task[None]


@dataclass
class SessionRuntime:
    """Mutable runtime state associated with one ChatSession."""

    session: ChatSession
    subscribers: set[asyncio.Queue[dict]] = field(
        default_factory=set
    )
    messages: list[ChatMessage] = field(
        default_factory=list
    )
    active_generation: ActiveGeneration | None = None


class ChatManager:
    """
    Manage TrackFlow WebSocket chat sessions.

    One generation task exists per session. All WebSocket clients
    subscribed to that session receive events from the same task,
    preventing duplicate calls to the First-line CX agent.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, SessionRuntime] = {}

        self._locks: defaultdict[str, asyncio.Lock] = (
            defaultdict(asyncio.Lock)
        )

    def get_session(
        self,
        session_id: str,
    ) -> ChatSession | None:
        """Return an existing ChatSession, if present."""
        runtime = self._sessions.get(session_id)

        if runtime is None:
            return None

        return runtime.session

    def get_messages(
        self,
        session_id: str,
    ) -> list[ChatMessage]:
        """Return the complete message history for a session."""
        runtime = self._sessions.get(session_id)

        if runtime is None:
            return []

        return list(runtime.messages)

    async def get_or_create_session(
        self,
        *,
        session_id: str,
        user_id: str,
        client_id: str,
    ) -> ChatSession:
        """
        Return the existing session or create it.

        Reconnecting with the same session_id attaches to the same
        runtime instead of creating a separate LangGraph conversation.
        """
        cleaned_session_id = session_id.strip()
        cleaned_user_id = user_id.strip()
        cleaned_client_id = client_id.strip()

        if not cleaned_session_id:
            raise ValueError(
                "session_id cannot be empty."
            )

        if not cleaned_user_id:
            raise ValueError(
                "user_id cannot be empty."
            )

        if not cleaned_client_id:
            raise ValueError(
                "client_id cannot be empty."
            )

        async with self._locks[cleaned_session_id]:
            existing = self._sessions.get(
                cleaned_session_id
            )

            if existing is not None:
                session = existing.session

                if session.user_id != cleaned_user_id:
                    raise ValueError(
                        "session_id is already associated "
                        "with another user."
                    )

                if session.client_id != cleaned_client_id:
                    raise ValueError(
                        "session_id is already associated "
                        "with another client."
                    )

                if session.status == "closed":
                    raise ValueError(
                        "Chat session is closed."
                    )

                return session

            session = ChatSession(
                session_id=cleaned_session_id,
                agent_id="first_line_cx",
                user_id=cleaned_user_id,
                client_id=cleaned_client_id,
                status="active",
            )

            self._sessions[cleaned_session_id] = (
                SessionRuntime(
                    session=session,
                )
            )

            return session

    async def subscribe(
        self,
        session_id: str,
    ) -> asyncio.Queue[dict]:
        """
        Subscribe one WebSocket connection to a session channel.

        This is the in-memory equivalent of subscribing to
        chat.<session_id>.
        """
        runtime = self._sessions.get(session_id)

        if runtime is None:
            raise ValueError(
                "Chat session does not exist."
            )

        queue: asyncio.Queue[dict] = asyncio.Queue()

        async with self._locks[session_id]:
            runtime.subscribers.add(queue)

        return queue

    async def unsubscribe(
        self,
        session_id: str,
        queue: asyncio.Queue[dict],
    ) -> None:
        """Remove one WebSocket from the session channel."""
        runtime = self._sessions.get(session_id)

        if runtime is None:
            return

        async with self._locks[session_id]:
            runtime.subscribers.discard(queue)

    async def publish(
        self,
        session_id: str,
        event: dict,
    ) -> None:
        """
        Publish one event to every chat.<session_id> subscriber.

        Every subscriber receives events from the same underlying
        agent generation task.
        """
        runtime = self._sessions.get(session_id)

        if runtime is None:
            return

        subscribers = list(runtime.subscribers)

        for queue in subscribers:
            await queue.put(event)

    async def start_generation(
        self,
        *,
        session_id: str,
        question: str,
    ) -> str:
        """
        Persist a user turn and start one assistant generation.

        Returns the assistant message_id.
        """
        cleaned_question = question.strip()

        if not cleaned_question:
            raise ValueError(
                "Input cannot be empty."
            )

        runtime = self._sessions.get(session_id)

        if runtime is None:
            raise ValueError(
                "Chat session does not exist."
            )

        async with self._locks[session_id]:
            active = runtime.active_generation

            if (
                active is not None
                and not active.task.done()
            ):
                raise RuntimeError(
                    "A generation is already active "
                    "for this session."
                )

            runtime.session.status = "active"

            user_message = ChatMessage(
                message_id=(
                    f"msg_{uuid4().hex[:12]}"
                ),
                session_id=session_id,
                role="user",
                content=cleaned_question,
                status="completed",
            )

            runtime.messages.append(user_message)

            assistant_message_id = (
                f"msg_{uuid4().hex[:12]}"
            )

            assistant_message = ChatMessage(
                message_id=assistant_message_id,
                session_id=session_id,
                role="assistant",
                content="",
                status="streaming",
            )

            runtime.messages.append(
                assistant_message
            )

            task = asyncio.create_task(
                self._run_generation(
                    session_id=session_id,
                    question=cleaned_question,
                    message=assistant_message,
                )
            )

            runtime.active_generation = (
                ActiveGeneration(
                    message_id=assistant_message_id,
                    task=task,
                )
            )

            return assistant_message_id

    async def _run_generation(
        self,
        *,
        session_id: str,
        question: str,
        message: ChatMessage,
    ) -> None:
        """Run one generation and broadcast its streamed output."""
        runtime = self._sessions[session_id]
        sequence = 0

        try:
            async for event in stream_agent(
                question=question,
                session_id=session_id,
            ):
                event_type = event.get("type")

                if event_type == "token":
                    token = str(
                        event.get("token", "")
                    )

                    if not token:
                        continue

                    message.content += token

                    await self.publish(
                        session_id,
                        {
                            "event": "token_chunk",
                            "data": {
                                "session_id": (
                                    session_id
                                ),
                                "token": token,
                                "sequence": sequence,
                            },
                        },
                    )

                    sequence += 1

                elif event_type == "completed":
                    message.status = "completed"
                    runtime.session.status = "active"

                    await self.publish(
                        session_id,
                        {
                            "event": (
                                "generation_completed"
                            ),
                            "data": {
                                "session_id": (
                                    session_id
                                ),
                                "message_id": (
                                    message.message_id
                                ),
                            },
                        },
                    )

        except asyncio.CancelledError:
            # interrupt_generation() owns the interrupted event.
            raise

        except Exception as exc:
            message.status = "error"

            await self.publish(
                session_id,
                {
                    "event": "generation_error",
                    "data": {
                        "session_id": session_id,
                        "message_id": (
                            message.message_id
                        ),
                        "error": str(exc),
                    },
                },
            )

        finally:
            async with self._locks[session_id]:
                active = runtime.active_generation

                if (
                    active is not None
                    and active.message_id
                    == message.message_id
                ):
                    runtime.active_generation = None

    async def interrupt_generation(
        self,
        *,
        session_id: str,
    ) -> str | None:
        """
        Abort the active generation task.

        Tokens already produced remain in the assistant message and
        that message is marked interrupted.
        """
        runtime = self._sessions.get(session_id)

        if runtime is None:
            raise ValueError(
                "Chat session does not exist."
            )

        async with self._locks[session_id]:
            active = runtime.active_generation

            if (
                active is None
                or active.task.done()
            ):
                return None

            message_id = active.message_id
            task = active.task

            message = next(
                (
                    item
                    for item in reversed(
                        runtime.messages
                    )
                    if (
                        item.message_id
                        == message_id
                    )
                ),
                None,
            )

            runtime.session.status = "interrupted"

            if message is not None:
                message.status = "interrupted"

            task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

        await self.publish(
            session_id,
            {
                "event": "generation_interrupted",
                "data": {
                    "session_id": session_id,
                    "message_id": message_id,
                    "status": "interrupted",
                },
            },
        )

        return message_id

    async def interrupt_and_redirect(
        self,
        *,
        session_id: str,
        new_input: str,
    ) -> str:
        """
        Abort the current answer and start a separate new user turn.

        The partial assistant response remains in history with
        status=interrupted. The redirected input is persisted as a
        new user message before its assistant generation begins.
        """
        cleaned_input = new_input.strip()

        if not cleaned_input:
            raise ValueError(
                "new_input cannot be empty."
            )

        await self.interrupt_generation(
            session_id=session_id,
        )

        return await self.start_generation(
            session_id=session_id,
            question=cleaned_input,
        )

    async def close_session(
        self,
        session_id: str,
    ) -> None:
        """Close a session and abort any active generation."""
        runtime = self._sessions.get(session_id)

        if runtime is None:
            return

        await self.interrupt_generation(
            session_id=session_id,
        )

        async with self._locks[session_id]:
            runtime.session.status = "closed"


chat_manager = ChatManager()