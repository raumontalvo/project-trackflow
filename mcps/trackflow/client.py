"""HTTP client used by the TrackFlow MCP tools."""

from __future__ import annotations

from typing import Any

import httpx

from mcps.trackflow.config import (
    TRACKFLOW_API_BASE_URL,
    TRACKFLOW_API_TIMEOUT_SECONDS,
)


class TrackFlowAPIError(RuntimeError):
    """Raised when the underlying TrackFlow API request fails."""


async def request_trackflow(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
) -> Any:
    """Call an existing TrackFlow API endpoint and return its JSON response."""

    url = f"{TRACKFLOW_API_BASE_URL}{path}"

    try:
        async with httpx.AsyncClient(
            timeout=TRACKFLOW_API_TIMEOUT_SECONDS
        ) as client:
            response = await client.request(
                method,
                url,
                params=params,
                json=json,
            )

    except httpx.TimeoutException as exc:
        raise TrackFlowAPIError(
            "The TrackFlow API request timed out."
        ) from exc

    except httpx.RequestError as exc:
        raise TrackFlowAPIError(
            "The TrackFlow API is currently unavailable."
        ) from exc

    if response.status_code == 404:
        raise TrackFlowAPIError("The requested TrackFlow resource was not found.")

    if response.status_code >= 400:
        try:
            detail = response.json().get("detail")
        except (ValueError, AttributeError):
            detail = response.text

        raise TrackFlowAPIError(
            f"TrackFlow API returned HTTP {response.status_code}: {detail}"
        )

    try:
        return response.json()
    except ValueError as exc:
        raise TrackFlowAPIError(
            "The TrackFlow API returned an invalid JSON response."
        ) from exc
