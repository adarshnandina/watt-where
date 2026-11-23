from datetime import date

from .base import ToolResult, check_technologies, error, query, resolve_area


def capacity_timeseries(
    area: str,
    technologies: list[str] | None = None,
    from_year: int = 2000,
    to_year: int | None = None,
    cumulative: bool = True,
) -> ToolResult:
    """Net capacity commissioned per year, optionally cumulative (minus decommissioned units)."""
    a, err = resolve_area(area)
    if err:
        return err
    techs, err = check_technologies(technologies)
    if err:
        return err
    to_year = to_year or date.today().year
    if not (1950 <= from_year <= to_year <= 2100):
        return error("Need 1950 <= from_year <= to_year <= 2100.")

    where, params = [a.unit_where, "u.status IN ('in_operation', 'decommissioned')",
                     "u.commissioning_date IS NOT NULL"], list(a.params)  # fmt: skip
    if techs:
        where.append("u.technology = ANY(%s)")
        params.append(techs)
    w = " AND ".join(where)

    # Two small aggregates (added per year, removed per year); the running sum is done in Python.
    added = query(
        f"""SELECT technology, extract(year FROM commissioning_date)::int y, sum(net_capacity_kw) kw
            FROM energy_energyunit u WHERE {w} GROUP BY 1, 2""",  # noqa: S608
        params,
    )
    removed = query(
        f"""SELECT technology, extract(year FROM decommissioning_date)::int y, sum(net_capacity_kw) kw
            FROM energy_energyunit u WHERE {w} AND u.status = 'decommissioned'
              AND u.decommissioning_date IS NOT NULL GROUP BY 1, 2""",  # noqa: S608
        params,
    )
    tech_list = techs or sorted({r["technology"] for r in added})
    years = list(range(from_year, to_year + 1))
    series, content_series = [], {}
    for t in tech_list:
        add = {r["y"]: r["kw"] or 0 for r in added if r["technology"] == t}
        rem = {r["y"]: r["kw"] or 0 for r in removed if r["technology"] == t}
        running = sum(v for y, v in add.items() if y < from_year) - sum(v for y, v in rem.items() if y < from_year)
        vals = []
        for y in years:
            if cumulative:
                running += add.get(y, 0) - rem.get(y, 0)
                vals.append(round(running / 1000, 2))
            else:
                vals.append(round(add.get(y, 0) / 1000, 2))
        series.append({"name": t, "values": vals})
        content_series[t] = dict(zip(map(str, years), vals, strict=True))

    if not series:
        return error("No units with a commissioning date match these filters.")
    mode = "cumulative installed" if cumulative else "newly commissioned per year"
    content = {
        "area": a.name, "mode": mode, "unit": "MW (net)", "from_year": from_year, "to_year": to_year,
        "decommissioning_accounted_for": cumulative, "series": content_series,
        "note": "Only units in operation or decommissioned (with a commissioning date) are counted; planned units excluded.",
    }  # fmt: skip
    display = [{"kind": "chart_line", "title": f"{a.name}: {mode} net capacity", "x": years,
                "series": series, "y_unit": "MW"}]  # fmt: skip
    last = ", ".join(f"{s['name']} {s['values'][-1]:,.1f} MW" for s in series)
    return ToolResult(content, display, f"{mode.capitalize()} {from_year}-{to_year} in {a.name}: {last}")
