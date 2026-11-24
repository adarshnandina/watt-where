"""Tool registry: the single source of truth for everything the LLM (or an MCP client) can do.

`REGISTRY[name]` -> Tool(fn, input_schema, description). Both the web agent and the MCP server
read from here, so a tool is written once and exposed twice.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import jsonschema

from .base import TECHNOLOGIES, ToolResult, error
from .capacity import capacity_summary, rank_municipalities
from .municipalities import find_municipality
from .spatial import units_near
from .sql_guard import DESCRIPTION as SQL_DESCRIPTION
from .sql_guard import run_readonly_sql
from .timeseries import capacity_timeseries

_TECH = {"type": "string", "enum": list(TECHNOLOGIES)}
_AREA = {
    "type": "string",
    "description": "'region' (all of Baden-Württemberg), a 5-digit district key, or an 8-digit municipality key (AGS) from find_municipality.",
}


@dataclass(frozen=True)
class Tool:
    name: str
    fn: Callable[..., ToolResult]
    description: str
    input_schema: dict


def _tool(name: str, fn: Callable[..., ToolResult], description: str, properties: dict, required: list[str]) -> Tool:
    schema = {"type": "object", "properties": properties, "required": required, "additionalProperties": False}
    return Tool(name, fn, description, schema)


_TOOLS = [
    _tool(
        "find_municipality", find_municipality,
        "Look up a municipality (Gemeinde/Stadt) OR a district (Landkreis) by name, tolerant of typos and umlauts. Returns "
        "municipality matches (8-digit key `ags`, district key, population, centre) and district matches (5-digit `district_ags`). "
        "ALWAYS call this first to turn a place name into a key; never guess a key.",
        {"query": {"type": "string", "description": "Place name, e.g. 'Freiburg' or 'Tuebingen'"},
         "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5}},
        ["query"],
    ),
    _tool(
        "capacity_summary", capacity_summary,
        "Installed capacity totals for an area: units, net capacity (MW), kW per inhabitant, and usable storage kWh, "
        "broken down by technology. Defaults: net capacity, units in operation. Also highlights the area on the map. "
        "Shows the CURRENT state: the commissioned_from/to filters only select units that are still in the chosen status today, "
        "so for historical totals ('at the end of 2020') or growth over time use capacity_timeseries instead.",
        {"area": _AREA,
         "technologies": {"type": "array", "items": _TECH, "description": "Omit for all technologies"},
         "status": {"type": "string", "enum": ["in_operation", "planned", "decommissioned", "other", "any"], "default": "in_operation"},
         "commissioned_from": {"type": "string", "description": "YYYY or YYYY-MM-DD"},
         "commissioned_to": {"type": "string", "description": "YYYY or YYYY-MM-DD"}},
        ["area"],
    ),
    _tool(
        "rank_municipalities", rank_municipalities,
        "Rank municipalities by a metric (units in operation, net capacity) and draw a choropleth map of all of them. "
        "For per-capita or per-area rankings set min_population (e.g. 1000) so tiny villages do not dominate, and mention it.",
        {"metric": {"type": "string", "enum": ["total_mw", "kw_per_capita", "unit_count", "mw_per_km2"]},
         "technology": _TECH,
         "district_ags": {"type": "string", "description": "5-digit district key to restrict the ranking"},
         "order": {"type": "string", "enum": ["desc", "asc"], "default": "desc"},
         "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
         "min_population": {"type": "integer", "minimum": 0, "default": 0}},
        ["metric"],
    ),
    _tool(
        "units_near", units_near,
        "Find units in operation within a radius of a municipality centre (municipality_ags) or a lat/lon point, drawn as map "
        "points. Only units with public coordinates can be found; the result reports how many lack coordinates.",
        {"lat": {"type": "number"}, "lon": {"type": "number"},
         "municipality_ags": {"type": "string", "description": "8-digit key; used as centre instead of lat/lon"},
         "radius_km": {"type": "number", "exclusiveMinimum": 0, "maximum": 100, "default": 10},
         "technology": _TECH,
         "min_capacity_kw": {"type": "number", "minimum": 0, "default": 0},
         "limit": {"type": "integer", "minimum": 1, "maximum": 2000, "default": 500}},
        [],
    ),
    _tool(
        "capacity_timeseries", capacity_timeseries,
        "Net capacity per year for an area, one series per technology, drawn as a line chart. cumulative=true gives installed "
        "capacity over time (decommissioned units removed); false gives capacity added per year.",
        {"area": _AREA,
         "technologies": {"type": "array", "items": _TECH},
         "from_year": {"type": "integer", "default": 2000},
         "to_year": {"type": "integer"},
         "cumulative": {"type": "boolean", "default": True}},
        ["area"],
    ),
    _tool(
        "run_readonly_sql", run_readonly_sql, SQL_DESCRIPTION,
        {"query": {"type": "string", "description": "One PostgreSQL SELECT statement"}},
        ["query"],
    ),
]  # fmt: skip

REGISTRY: dict[str, Tool] = {t.name: t for t in _TOOLS}


def anthropic_tool_definitions() -> list[dict]:
    """Tool definitions in the Anthropic API format; the last one carries the prompt-cache marker."""
    defs = [{"name": t.name, "description": t.description, "input_schema": t.input_schema} for t in _TOOLS]
    defs[-1]["cache_control"] = {"type": "ephemeral"}
    return defs


def call_tool(name: str, arguments: dict[str, Any]) -> tuple[ToolResult, int]:
    """Validate arguments against the tool's JSON schema, run it, return (result, duration_ms).

    Never raises for bad input or tool bugs: the failure is returned as an error result the
    model can read and react to.
    """
    started = time.monotonic()
    tool = REGISTRY.get(name)
    if tool is None:
        result = error(f"Unknown tool '{name}'", available=list(REGISTRY))
    else:
        try:
            jsonschema.validate(arguments or {}, tool.input_schema)
            result = tool.fn(**(arguments or {}))
        except jsonschema.ValidationError as e:
            result = error(f"Invalid arguments: {e.message}")
        except Exception:  # a bug in a tool must not kill the whole conversation
            import logging

            logging.getLogger(__name__).exception("tool %s failed", name)
            result = error("The tool failed unexpectedly.")
    return result, int((time.monotonic() - started) * 1000)
