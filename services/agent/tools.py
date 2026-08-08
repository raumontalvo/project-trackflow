"""MCP-backed external tools used by the TrackFlow support agent."""

from __future__ import annotations

import os

import httpx
from dotenv import load_dotenv

load_dotenv()
from datetime import datetime
from typing import Literal

from langchain_mcp_adapters.client import MultiServerMCPClient
from pydantic import BaseModel, ValidationError


MCP_SERVER_URL = os.getenv(
    "MCP_SERVER_URL",
    "http://localhost:8001/mcp",
)

MCP_OAUTH_TOKEN_URL = os.getenv(
    "MCP_OAUTH_TOKEN_URL",
    "http://localhost:9000/realms/trackflow/protocol/openid-connect/token",
)
MCP_OAUTH_CLIENT_ID = os.getenv(
    "MCP_OAUTH_CLIENT_ID",
    "trackflow-mcp-client",
)
MCP_OAUTH_CLIENT_SECRET = os.getenv(
    "MCP_OAUTH_CLIENT_SECRET",
    "",
)


class TicketLookupInput(BaseModel):
    """Typed input contract for an incident lookup."""

    incident_id: int


class IncidentRecord(BaseModel):
    """Incident fields returned by the TrackFlow MCP server."""

    id: int
    title: str
    description: str
    category: str
    status: Literal["open", "in_progress", "resolved", "discarded"]
    origin: Literal["customer", "branch", "internal"]
    branch: Literal[
        "central",
        "la_warehouse",
        "la_office",
        "zaragoza_warehouse",
        "zaragoza_office",
    ]
    created_at: datetime
    updated_at: datetime


class TicketLookupResult(BaseModel):
    """Typed result returned to the LangGraph workflow."""

    success: bool
    incident: IncidentRecord | None = None
    error: str | None = None


async def _get_access_token() -> str:
    """Request a least-privilege incidents:read OAuth access token."""

    if not MCP_OAUTH_CLIENT_SECRET:
        raise RuntimeError("The MCP OAuth client secret is not configured.")

    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post(
            MCP_OAUTH_TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": MCP_OAUTH_CLIENT_ID,
                "client_secret": MCP_OAUTH_CLIENT_SECRET,
                "scope": "incidents:read",
            },
        )

    response.raise_for_status()

    token = response.json().get("access_token")

    if not token:
        raise RuntimeError("The OAuth server did not return an access token.")

    return token


def _build_mcp_client(access_token: str) -> MultiServerMCPClient:
    """Create the authenticated TrackFlow MCP client used by the agent."""

    return MultiServerMCPClient(
        {
            "trackflow": {
                "transport": "streamable_http",
                "url": MCP_SERVER_URL,
                "headers": {
                    "Authorization": f"Bearer {access_token}",
                },
            }
        }
    )

async def lookup_ticket(payload: TicketLookupInput) -> TicketLookupResult:
    """Read current incident data through the OAuth-protected MCP server."""

    try:
        access_token = await _get_access_token()
        client = _build_mcp_client(access_token)

        tools = await client.get_tools(server_name="trackflow")

        get_incident_tool = next(
            (tool for tool in tools if tool.name == "get_incident"),
            None,
        )

        if get_incident_tool is None:
            return TicketLookupResult(
                success=False,
                error="The MCP server did not expose the get_incident tool.",
            )

        result = await get_incident_tool.ainvoke(
            {"incident_id": payload.incident_id}
        )

        if isinstance(result, dict):
            incident_data = result
        elif hasattr(result, "content"):
            incident_data = result.content
        else:
            incident_data = result

        if isinstance(incident_data, list):
            if not incident_data:
                return TicketLookupResult(
                    success=False,
                    error="The MCP server returned an empty incident response.",
                )

            first = incident_data[0]

            if hasattr(first, "text"):
                import json

                incident_data = json.loads(first.text)

        incident = IncidentRecord.model_validate(incident_data)

        return TicketLookupResult(
            success=True,
            incident=incident,
        )

    except ValidationError:
        return TicketLookupResult(
            success=False,
            error="The MCP server returned an invalid incident response.",
        )

    except Exception as error:
        return TicketLookupResult(
            success=False,
            error=f"The MCP incident lookup failed: {error}",
        )
