"""Configuration for the TrackFlow MCP server."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

TRACKFLOW_API_BASE_URL = os.getenv(
    "TRACKFLOW_API_BASE_URL",
    "http://localhost:8000",
).rstrip("/")

TRACKFLOW_API_TIMEOUT_SECONDS = float(
    os.getenv("TRACKFLOW_API_TIMEOUT_SECONDS", "5")
)

MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8001"))

MCP_RESOURCE_URL = os.getenv(
    "MCP_RESOURCE_URL",
    f"http://localhost:{MCP_PORT}",
)

MCP_AUTH_ISSUER = os.getenv(
    "MCP_AUTH_ISSUER",
    "http://localhost:9000",
)

INCIDENT_READ_SCOPE = "incidents:read"
INCIDENT_WRITE_SCOPE = "incidents:write"
INVENTORY_READ_SCOPE = "inventory:read"
