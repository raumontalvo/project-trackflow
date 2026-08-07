"""Focused tests for the TrackFlow MCP integration."""

from __future__ import annotations

from pathlib import Path

import pytest

from fastmcp.exceptions import ToolError

from mcps.trackflow.server import mcp


@pytest.mark.asyncio
async def test_mcp_discovers_expected_tools() -> None:
    """External MCP clients should discover the documented company tools."""
    tools = await mcp.list_tools()
    names = {tool.name for tool in tools}

    assert {
        "get_incident",
        "list_incidents",
        "get_incident_summary",
        "create_incident",
        "update_incident_status",
        "list_inventory_products",
        "get_inventory_product",
        "list_inventory_movements",
        "inventory_write_attempt",
    }.issubset(names)


@pytest.mark.asyncio
async def test_inventory_write_is_explicitly_rejected() -> None:
    """Inventory mutations must be forbidden through MCP by design."""

    with pytest.raises(
        ToolError,
        match="Inventory mutations are forbidden",
    ):
        await mcp.call_tool(
            "inventory_write_attempt",
            {"action": "create_outbound_order"},
        )


def test_agent_has_no_direct_incident_api_call() -> None:
    """The agent must consume incidents through MCP, not the backend directly."""
    source = Path("services/agent/tools.py").read_text(encoding="utf-8")

    assert "INCIDENT_API_BASE_URL" not in source
    assert "/api/incidents" not in source
