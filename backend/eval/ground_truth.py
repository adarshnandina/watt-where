"""Ground truth for the eval, computed straight from the database with hand-written SQL.

Deliberately does NOT import energy.tools: the point is an independent check of the tools and
the agent. Nothing in questions.yaml is hand-typed; every expected number comes from here.
"""

from __future__ import annotations

from django.db import connection

from energy.textnorm import normalize_name


def _q(sql: str, params: list | None = None) -> list[tuple]:
    with connection.cursor() as cur:
        cur.execute(sql, params or [])
        return cur.fetchall()


def _scope(municipality: str | None, district: str | None) -> tuple[str, list]:
    """SQL condition on units `u` for a municipality / district given by (exact) name, or the region."""
    if municipality:
        return "u.municipality_id = (SELECT ags FROM energy_municipality WHERE name = %s)", [municipality]
    if district:
        return (
            "u.municipality_id IN (SELECT ags FROM energy_municipality WHERE district_name = %s)",
            [district],
        )
    return "TRUE", []


def capacity(municipality=None, district=None, technology=None, status="in_operation") -> dict:
    scope, p = _scope(municipality, district)
    tech = "AND u.technology = %s" if technology else ""
    params = p + ([technology] if technology else []) + [status]
    n, kw, kwh = _q(
        f"""SELECT count(*), coalesce(sum(net_capacity_kw), 0), coalesce(sum(storage_capacity_kwh), 0)
            FROM energy_energyunit u WHERE {scope} {tech} AND u.status = %s""",  # noqa: S608
        params,
    )[0]
    return {"units": int(n), "mw": kw / 1000, "storage_mwh": kwh / 1000}


def population(municipality: str) -> dict:
    return {"population": _q("SELECT population FROM energy_municipality WHERE name = %s", [municipality])[0][0]}


_METRIC = {
    "total_mw": "coalesce(s.kw, 0) / 1000.0",
    "kw_per_capita": "coalesce(s.kw, 0) / nullif(m.population, 0)",
    "unit_count": "coalesce(s.n, 0)",
    "mw_per_km2": "coalesce(s.kw, 0) / 1000.0 / nullif(m.area_km2, 0)",
}


def ranking(metric, technology=None, district=None, min_population=0, limit=10) -> dict:
    tech = "AND technology = %s" if technology else ""
    rows = _q(
        f"""SELECT m.name, {_METRIC[metric]} AS v
            FROM energy_municipality m
            LEFT JOIN (SELECT municipality_id, count(*) n, sum(net_capacity_kw) kw FROM energy_energyunit
                       WHERE status = 'in_operation' {tech} GROUP BY 1) s ON s.municipality_id = m.ags
            WHERE m.population >= %s {"AND m.district_name = %s" if district else ""}
            ORDER BY v DESC NULLS LAST, m.name LIMIT %s""",  # noqa: S608
        ([technology] if technology else []) + [min_population] + ([district] if district else []) + [limit],
    )
    return {"names": [r[0] for r in rows], "top1_name": rows[0][0], "top1_value": float(rows[0][1])}


def near(municipality: str, radius_km: float, technology=None, min_kw=0) -> dict:
    tech = "AND u.technology = %s" if technology else ""
    n, kw = _q(
        f"""SELECT count(*), coalesce(sum(u.net_capacity_kw), 0)
            FROM energy_energyunit u,
                 (SELECT centroid_lon lon, centroid_lat lat FROM energy_municipality WHERE name = %s) c
            WHERE u.status = 'in_operation' AND u.geom IS NOT NULL {tech} AND u.net_capacity_kw >= %s
              AND ST_DWithin(u.geom::geography, ST_SetSRID(ST_MakePoint(c.lon, c.lat), 4326)::geography, %s)""",  # noqa: S608
        [municipality] + ([technology] if technology else []) + [min_kw, radius_km * 1000],
    )[0]
    return {"units": int(n), "mw": kw / 1000}


def largest_near(municipality: str, radius_km: float, technology: str) -> dict:
    rows = _q(
        """SELECT u.net_capacity_kw FROM energy_energyunit u,
                (SELECT centroid_lon lon, centroid_lat lat FROM energy_municipality WHERE name = %s) c
           WHERE u.status = 'in_operation' AND u.geom IS NOT NULL AND u.technology = %s
             AND ST_DWithin(u.geom::geography, ST_SetSRID(ST_MakePoint(c.lon, c.lat), 4326)::geography, %s)
           ORDER BY u.net_capacity_kw DESC LIMIT 3""",
        [municipality, technology, radius_km * 1000],
    )
    return {"largest_kw": float(rows[0][0]), "largest_mw": float(rows[0][0]) / 1000}


def installed_at_end_of(year: int, municipality=None, district=None, technology=None) -> dict:
    """Cumulative net MW at the end of `year`: commissioned by then and not decommissioned by then."""
    scope, p = _scope(municipality, district)
    kw = _q(
        f"""SELECT coalesce(sum(net_capacity_kw), 0) FROM energy_energyunit u
            WHERE {scope} AND u.technology = %s AND u.status IN ('in_operation', 'decommissioned')
              AND u.commissioning_date <= make_date(%s, 12, 31)
              AND (u.decommissioning_date IS NULL OR u.decommissioning_date > make_date(%s, 12, 31))""",  # noqa: S608
        p + [technology, year, year],
    )[0][0]
    return {"mw": kw / 1000}


def added_in_year(year: int, municipality=None, district=None, technology=None) -> dict:
    scope, p = _scope(municipality, district)
    kw = _q(
        f"""SELECT coalesce(sum(net_capacity_kw), 0) FROM energy_energyunit u
            WHERE {scope} AND u.technology = %s AND u.status IN ('in_operation', 'decommissioned')
              AND extract(year FROM u.commissioning_date) = %s""",  # noqa: S608
        p + [technology, year],
    )[0][0]
    return {"mw": kw / 1000}


def best_year(municipality: str, technology: str) -> dict:
    scope, p = _scope(municipality, None)
    y, kw = _q(
        f"""SELECT extract(year FROM commissioning_date)::int y, sum(net_capacity_kw) FROM energy_energyunit u
            WHERE {scope} AND technology = %s AND status IN ('in_operation', 'decommissioned')
            GROUP BY 1 ORDER BY 2 DESC LIMIT 1""",  # noqa: S608
        p + [technology],
    )[0]
    return {"year": int(y), "mw": float(kw) / 1000}


def storage_over_kwh(kwh: float) -> dict:
    return {
        "units": int(
            _q(
                "SELECT count(*) FROM energy_energyunit WHERE technology='storage' AND storage_capacity_kwh > %s", [kwh]
            )[0][0]
        )
    }


def ambiguous_name(name: str) -> dict:
    rows = _q("SELECT district_name FROM energy_municipality WHERE name = %s ORDER BY 1", [name])
    return {"districts": [normalize_name(r[0]) for r in rows], "n": len(rows)}


def none() -> dict:
    return {}
