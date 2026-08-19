"""Integration tests for the TrackFlow SSE HTTP endpoint."""

import asyncio
import os

os.environ.setdefault(
    "DATABASE_URL",
    "sqlite:///./test_sse_endpoint.db",
)
os.environ.setdefault(
    "SECRET_KEY",
    "test-secret-key",
)

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from services.api.routes.notifications import (
    notification_stream,
    router,
)


app = FastAPI()
app.include_router(router)


def test_sse_endpoint_requires_authentication() -> None:
    client = TestClient(app)

    response = client.get("/notifications/stream")

    assert response.status_code == 401


def test_sse_endpoint_returns_event_stream_when_authenticated() -> None:
    async def scenario() -> None:
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/notifications/stream",
                "headers": [],
                "query_string": b"",
                "server": ("testserver", 80),
                "client": ("127.0.0.1", 12345),
                "scheme": "http",
            }
        )

        response = await notification_stream(
            request,
            _current_user={
                "id": 1,
                "email": "sales@trackflow.test",
            },
        )

        assert response.status_code == 200
        assert response.media_type == "text/event-stream"
        assert response.headers["cache-control"] == "no-cache"

        await response.body_iterator.aclose()

    asyncio.run(scenario())
