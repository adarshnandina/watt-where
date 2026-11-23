"""Shared pieces of the tool layer: the ToolResult contract, DB helpers, area/filter parsing.

Design point: big payloads (GeoJSON, full tables) go to `display` (frontend only); the LLM
only ever sees the compact `llm_content`. That keeps tokens, cost and latency down and
leaves the model fewer numbers to garble.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from django.db import connection

TECHNOLOGIES = ("solar", "wind", "biomass", "hydro", "storage")
STATUSES = ("in_operation", "planned", "decommissioned", "other", "any")


@dataclass
class ToolResult:
    llm_content: dict  # compact data for the model
    display: list[dict] = field(default_factory=list)  # UI payloads, never sent to the model
    summary: str = ""  # one-liner for the tool-call chip

    @property
    def ok(self) -> bool:
        return "error" not in self.llm_content


def error(message: str, **extra: Any) -> ToolResult:
    """Errors are returned as data (the model can read them and recover), never raised."""
    return ToolResult(llm_content={"error": message, **extra}, summary=f"Error: {message}")


def jsonable(v: Any) -> Any:
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, date):
        return v.isoformat()
    return v


def query(sql: str, params: list | tuple | None = None) -> list[dict]:
    """Run a parameterized SELECT on the default connection; rows as dicts.

    Only ever called with constant SQL text; user values always travel in `params`.
    """
    with connection.cursor() as cur:
        cur.execute(sql, params or [])
        cols = [c.name for c in cur.description]
        return [dict(zip(cols, (jsonable(v) for v in row), strict=True)) for row in cur.fetchall()]


def mw(kw: float | None, digits: int = 2) -> float:
    return round((kw or 0) / 1000, digits)


def fmt_int(n: float | int) -> str:
    return f"{int(round(n)):,}"


def check_technologies(technologies: list[str] | None) -> tuple[list[str] | None, ToolResult | None]:
    if not technologies:
        return None, None
    norm = [t.strip().lower() for t in technologies]
    bad = [t for t in norm if t not in TECHNOLOGIES]
    if bad:
        return None, error(f"Unknown technology {bad}", allowed=list(TECHNOLOGIES))
    return norm, None


def check_status(status: str) -> ToolResult | None:
    if status not in STATUSES:
        return error(f"Unknown status '{status}'", allowed=list(STATUSES))
    return None


def parse_date(s: str | None, end: bool = False) -> tuple[date | None, ToolResult | None]:
    """Accept 'YYYY' or 'YYYY-MM-DD'. A bare year means Jan 1 (start) or Dec 31 (end)."""
    if s is None or s == "":
        return None, None
    s = str(s).strip()
    try:
        if re.fullmatch(r"\d{4}", s):
            return (date(int(s), 12, 31) if end else date(int(s), 1, 1)), None
        return date.fromisoformat(s), None
    except ValueError:
        return None, error(f"Invalid date '{s}'. Use YYYY or YYYY-MM-DD.")


@dataclass
class Area:
    kind: str  # municipality | district | region
    code: str
    name: str
    population: int | None
    unit_where: str  # SQL fragment on alias `u`
    params: list

    @property
    def label(self) -> str:
        return self.name


def resolve_area(area: str) -> tuple[Area | None, ToolResult | None]:
    """'region' | 5-digit district key | 8-digit municipality key -> Area (or an error)."""
    from django.conf import settings

    area = (area or "").strip()
    if area.lower() == "region":
        row = query("SELECT sum(population) p FROM energy_municipality")[0]
        return Area("region", "region", settings.REGION_NAME, row["p"], "TRUE", []), None
    if re.fullmatch(r"\d{8}", area):
        rows = query("SELECT name, population FROM energy_municipality WHERE ags=%s", [area])
        if not rows:
            return None, error(f"No municipality with key {area}. Use find_municipality first.")
        return Area("municipality", area, rows[0]["name"], rows[0]["population"],
                    "u.municipality_id = %s", [area]), None  # fmt: skip
    if re.fullmatch(r"\d{5}", area):
        rows = query(
            "SELECT max(district_name) n, sum(population) p, count(*) c FROM energy_municipality WHERE district_ags=%s",
            [area],
        )
        if not rows[0]["c"]:
            return None, error(f"No district with key {area}. Use find_municipality to look up the district key.")
        return Area("district", area, rows[0]["n"], rows[0]["p"],
                    "u.municipality_id IN (SELECT ags FROM energy_municipality WHERE district_ags = %s)",
                    [area]), None  # fmt: skip
    return None, error(
        f"Invalid area '{area}': use 'region', a 5-digit district key or an 8-digit municipality key "
        "(get it from find_municipality)."
    )


def geojson_feature(geom_json: str | None, properties: dict) -> dict:
    return {"type": "Feature", "geometry": json.loads(geom_json) if geom_json else None, "properties": properties}


def feature_collection(features: list[dict]) -> dict:
    return {"type": "FeatureCollection", "features": features}
