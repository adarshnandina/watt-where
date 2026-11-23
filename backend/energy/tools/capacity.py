from .base import (
    Area,
    ToolResult,
    check_status,
    check_technologies,
    error,
    feature_collection,
    fmt_int,
    geojson_feature,
    mw,
    parse_date,
    query,
    resolve_area,
)  # fmt: skip


def capacity_summary(
    area: str,
    technologies: list[str] | None = None,
    status: str = "in_operation",
    commissioned_from: str | None = None,
    commissioned_to: str | None = None,
) -> ToolResult:
    """Unit count, net capacity (MW), per-inhabitant capacity and storage kWh by technology."""
    a, err = resolve_area(area)
    if err:
        return err
    techs, err = check_technologies(technologies)
    if err:
        return err
    if err := check_status(status):
        return err
    d_from, err = parse_date(commissioned_from)
    if err:
        return err
    d_to, err = parse_date(commissioned_to, end=True)
    if err:
        return err

    where, params = [a.unit_where], list(a.params)
    if techs:
        where.append("u.technology = ANY(%s)")
        params.append(techs)
    if status != "any":
        where.append("u.status = %s")
        params.append(status)
    if d_from:
        where.append("u.commissioning_date >= %s")
        params.append(d_from)
    if d_to:
        where.append("u.commissioning_date <= %s")
        params.append(d_to)

    rows = query(
        f"""SELECT u.technology, count(*) AS units, coalesce(sum(u.net_capacity_kw), 0) AS net_kw,
                   sum(u.storage_capacity_kwh) AS storage_kwh
            FROM energy_energyunit u WHERE {" AND ".join(where)}
            GROUP BY u.technology ORDER BY net_kw DESC""",  # noqa: S608 (fragments are constants)
        params,
    )
    pop = a.population or 0
    by_tech = []
    for r in rows:
        item = {
            "technology": r["technology"],
            "units": r["units"],
            "net_capacity_kw": round(r["net_kw"], 1),
            "net_capacity_mw": mw(r["net_kw"]),
            "kw_per_inhabitant": round(r["net_kw"] / pop, 3) if pop else None,
        }
        if r["storage_kwh"] is not None:
            item["usable_storage_kwh"] = round(r["storage_kwh"], 1)
        by_tech.append(item)
    total_kw = sum(r["net_kw"] for r in rows)
    total_units = sum(r["units"] for r in rows)
    content = {
        "area": a.name, "area_kind": a.kind, "area_key": a.code, "population": a.population,
        "filters": {"technologies": techs, "status": status,
                    "commissioned_from": commissioned_from, "commissioned_to": commissioned_to},
        "basis": "net capacity (Nettonennleistung)",
        "total_units": total_units,
        "total_net_capacity_kw": round(total_kw, 1),
        "total_net_capacity_mw": mw(total_kw),
        "total_kw_per_inhabitant": round(total_kw / pop, 3) if pop else None,
        "by_technology": by_tech,
    }  # fmt: skip
    if not rows:
        content["note"] = "No units match these filters."

    display = [{
        "kind": "table", "title": f"Capacity in {a.name}",
        "columns": ["Technology", "Units", "Net capacity (MW)", "kW per inhabitant"],
        "rows": [[t["technology"], t["units"], t["net_capacity_mw"], t["kw_per_inhabitant"]] for t in by_tech],
    }]  # fmt: skip
    hl = _highlight(a)
    if hl:
        display.append(hl)
    label = ", ".join(techs) if techs else "all technologies"
    summary = f"{fmt_int(total_units)} units ({label}) in {a.name}: {total_kw / 1000:,.1f} MW"
    return ToolResult(content, display, summary)


def _highlight(a: Area) -> dict | None:
    if a.kind == "region":
        return None  # the whole region is the default map view
    where, p = ("ags = %s", [a.code]) if a.kind == "municipality" else ("district_ags = %s", [a.code])
    rows = query(
        f"SELECT ags, name, ST_AsGeoJSON(geom_simplified, 4) AS g FROM energy_municipality WHERE {where}",  # noqa: S608
        p,
    )
    feats = [geojson_feature(r["g"], {"ags": r["ags"], "name": r["name"]}) for r in rows]
    return {"kind": "map_highlight", "title": a.name, "geojson": feature_collection(feats)}


METRICS = {
    # metric -> SQL expression over aliases m (municipality) and s (unit aggregates)
    "total_mw": ("coalesce(s.kw, 0) / 1000.0", "MW"),
    "kw_per_capita": ("CASE WHEN m.population > 0 THEN coalesce(s.kw, 0) / m.population END", "kW per inhabitant"),
    "unit_count": ("coalesce(s.n, 0)::float", "units"),
    "mw_per_km2": ("CASE WHEN m.area_km2 > 0 THEN coalesce(s.kw, 0) / 1000.0 / m.area_km2 END", "MW per km²"),
}  # fmt: skip


def rank_municipalities(
    metric: str,
    technology: str | None = None,
    district_ags: str | None = None,
    order: str = "desc",
    limit: int = 10,
    min_population: int = 0,
) -> ToolResult:
    """Top-N municipalities by a metric (net capacity, units in operation), plus a choropleth."""
    if metric not in METRICS:
        return error(f"Unknown metric '{metric}'", allowed=list(METRICS))
    if order not in ("asc", "desc"):
        return error("order must be 'asc' or 'desc'")
    techs, err = check_technologies([technology] if technology else None)
    if err:
        return err
    if district_ags and not (len(district_ags) == 5 and district_ags.isdigit()):
        return error("district_ags must be a 5-digit district key (from find_municipality).")
    limit = max(1, min(int(limit), 50))
    expr, unit = METRICS[metric]

    unit_filter, uparams = "status = 'in_operation'", []
    if techs:
        unit_filter += " AND technology = %s"
        uparams.append(techs[0])
    mfilter, mparams = "TRUE", []
    if district_ags:
        mfilter, mparams = "m.district_ags = %s", [district_ags]

    # `expr` and `order` come from fixed maps/validated enums above, never from user text.
    sql = f"""
        SELECT m.ags, m.name, m.district_name, m.population, coalesce(s.n, 0) AS units,
               coalesce(s.kw, 0) AS kw, ({expr}) AS value, ST_AsGeoJSON(m.geom_simplified, 4) AS g
        FROM energy_municipality m
        LEFT JOIN (SELECT municipality_id, count(*) n, sum(net_capacity_kw) kw
                   FROM energy_energyunit WHERE {unit_filter} GROUP BY municipality_id) s
          ON s.municipality_id = m.ags
        WHERE {mfilter}
    """  # noqa: S608
    rows = query(sql, uparams + mparams)
    if not rows:
        return error("No municipalities in scope.")

    eligible = [r for r in rows if r["value"] is not None and (r["population"] or 0) >= min_population]
    eligible.sort(key=lambda r: r["value"], reverse=(order == "desc"))
    top = eligible[:limit]
    digits = 3 if metric in ("kw_per_capita", "mw_per_km2") else 1
    top_out = [
        {"rank": i + 1, "ags": r["ags"], "name": r["name"], "district": r["district_name"],
         "population": r["population"], "units": r["units"], "net_capacity_mw": mw(r["kw"]),
         metric: round(r["value"], digits)}
        for i, r in enumerate(top)
    ]  # fmt: skip
    scope = f"district {district_ags}" if district_ags else "the whole region"
    content = {
        "metric": metric, "unit": unit, "technology": techs[0] if techs else "all", "status": "in_operation",
        "basis": "net capacity", "scope": scope, "order": order, "min_population": min_population,
        "municipalities_considered": len(eligible), "top": top_out,
    }  # fmt: skip
    if metric in ("kw_per_capita", "mw_per_km2") and min_population == 0:
        content["note"] = "No minimum population applied; tiny villages can dominate per-capita rankings."

    feats = [geojson_feature(r["g"], {"ags": r["ags"], "name": r["name"], "value": round(r["value"], 4)
                                      if r["value"] is not None else None}) for r in rows]  # fmt: skip
    tech_label = techs[0] if techs else "all technologies"
    title = f"{tech_label} - {unit}"
    display = [
        {"kind": "map_choropleth", "title": title, "unit": unit, "geojson": feature_collection(feats)},
        {"kind": "table", "title": f"Top {len(top_out)} by {unit}",
         "columns": ["#", "Municipality", "District", "Population", f"Value ({unit})"],
         "rows": [[t["rank"], t["name"], t["district"], t["population"], t[metric]] for t in top_out]},
    ]  # fmt: skip
    first = top_out[0]["name"] if top_out else "-"
    return ToolResult(content, display, f"Ranked {len(eligible):,} municipalities by {unit}; #1: {first}")
