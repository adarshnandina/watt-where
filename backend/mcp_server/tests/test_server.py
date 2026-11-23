"""MCP server tests (in-process, on the synthetic seed data)."""

import json

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from energy.tools import REGISTRY
from mcp_server.server import mcp

pytestmark = pytest.mark.django_db


async def test_lists_exactly_the_registry_tools_with_registry_schemas():
    tools = {t.name: t for t in await mcp.list_tools()}
    assert set(tools) == set(REGISTRY)
    schema = tools["capacity_summary"].input_schema
    assert schema["properties"]["technologies"]["items"]["enum"] == ["solar", "wind", "biomass", "hydro", "storage"]
    assert tools["run_readonly_sql"].description == REGISTRY["run_readonly_sql"].description


async def test_call_returns_summary_and_llm_content_without_display_payloads():
    result = await mcp.call_tool("capacity_summary", {"area": "08311000"}, None)
    body = json.loads(result.content[0].text)
    assert body["summary"] and body["result"]["area"] == "Freiburg im Breisgau"
    assert "geojson" not in json.dumps(body)  # map layers are for the web UI only


async def test_unset_optional_arguments_are_treated_as_omitted():
    result = await mcp.call_tool("rank_municipalities", {"metric": "unit_count"}, None)
    assert json.loads(result.content[0].text)["result"]["top"]


async def test_tool_errors_surface_as_mcp_errors():
    with pytest.raises(ToolError, match="Invalid area"):
        await mcp.call_tool("capacity_summary", {"area": "nope"}, None)


async def test_schema_resource():
    contents = await mcp.read_resource("wattwhere://schema", None)
    text = contents[0].content if hasattr(contents[0], "content") else contents[0].text
    assert "energy_energyunit" in text and "kW" in text
