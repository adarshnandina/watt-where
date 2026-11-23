"""MCP server: the same tool layer as the web agent, exposed over stdio.

    uv run --directory <repo>/backend python -m mcp_server.server

One tool layer, two front doors: `energy.tools.REGISTRY` feeds both this server and the web
agent loop, so a tool is written (and tested) exactly once.

IMPORTANT: with the stdio transport, stdout IS the protocol channel. Never print to stdout;
logs go to stderr.
"""

from __future__ import annotations

import inspect
import json
import logging
import os
import sys

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402
from django.db import connections  # noqa: E402

django.setup()  # the tools use the Django ORM connection

from mcp.server.mcpserver import MCPServer  # noqa: E402
from mcp.server.mcpserver.exceptions import ToolError  # noqa: E402

from energy.tools import REGISTRY, Tool, call_tool  # noqa: E402
from energy.tools.sql_guard import DESCRIPTION as SQL_DESCRIPTION  # noqa: E402

mcp = MCPServer(
    "wattwhere",
    instructions=(
        "Questions about solar, wind, biomass, hydro and battery storage units and municipalities in "
        "Baden-Württemberg (Marktstammdatenregister + BKG boundaries). Call find_municipality first to turn a "
        "place name into a key. Capacities are net, units in operation, unless stated otherwise."
    ),
)

SCHEMA_MARKDOWN = f"""# WattWhere database schema

Data: Marktstammdatenregister (Bundesnetzagentur, dl-de/by-2-0) and BKG VG250-EW (dl-de/by-2-0).
All capacities are **kW** (net unless noted). Only units *with coordinates* have a `geom`; most rooftop
solar and home batteries have none (privacy), so use municipality aggregates for totals.

{SQL_DESCRIPTION}

## Tool conventions
- `area` arguments: `"region"`, a 5-digit district key or an 8-digit municipality key (from `find_municipality`).
- Results state the basis (net capacity, units in operation) and caveats explicitly.
"""


def _register(tool: Tool) -> None:
    def handler(**kwargs):
        # The SDK passes unset optional parameters as None; the registry's schema means "omitted".
        args = {k: v for k, v in kwargs.items() if v is not None}
        try:
            result, _ms = call_tool(tool.name, args)  # validates against the registry's JSON schema
        finally:
            connections.close_all()  # the SDK runs sync tools in worker threads; don't leak their connections
        if not result.ok:
            raise ToolError(result.llm_content["error"])  # -> MCP isError result
        # llm_content as JSON plus the one-line summary. Display payloads (GeoJSON...) are left out.
        return json.dumps({"summary": result.summary, "result": result.llm_content}, ensure_ascii=False, default=str)

    # Same parameters (names, type hints, defaults) as the real function, but the MCP handler returns text.
    handler.__signature__ = inspect.signature(tool.fn).replace(return_annotation=str)  # type: ignore[attr-defined]
    handler.__annotations__ = {**tool.fn.__annotations__, "return": str}
    mcp.add_tool(handler, name=tool.name, description=tool.description)
    # Advertise the registry's richer JSON schema (enums, ranges, descriptions) to clients.
    # (_tool_manager is an internal attribute of the SDK; the public API only infers a schema from type hints.)
    mcp._tool_manager.get_tool(tool.name).parameters = tool.input_schema


for _tool in REGISTRY.values():
    _register(_tool)


@mcp.resource("wattwhere://schema", name="schema", title="WattWhere schema", mime_type="text/markdown")
def schema() -> str:
    """Markdown description of the tables and columns."""
    return SCHEMA_MARKDOWN


if __name__ == "__main__":
    mcp.run("stdio")
