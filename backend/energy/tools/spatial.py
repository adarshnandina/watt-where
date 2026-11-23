import json

from .base import (
    ToolResult,
    check_technologies,
    error,
    feature_collection,
    fmt_int,
    geojson_feature,
    mw,
    query,
)  # fmt: skip

MAX_RADIUS_KM = 100


def units_near(
    lat: float | None = None,
    lon: float | None = None,
    municipality_ags: str | None = None,
    radius_km: float = 10,
    technology: str | None = None,
    min_capacity_kw: float = 0,
    limit: int = 500,
) -> ToolResult:
    """Units in operation within radius_km of a point (or a municipality's centre).

    Only units WITH public coordinates can be found; the result states how many units in the
    nearby municipalities have none (most rooftop solar), because that's a real data gap.
    """
    if municipality_ags:
        rows = query(
            "SELECT name, centroid_lat, centroid_lon FROM energy_municipality WHERE ags = %s", [municipality_ags]
        )
        if not rows:
            return error(f"No municipality with key {municipality_ags}. Use find_municipality first.")
        lat, lon, center_name = rows[0]["centroid_lat"], rows[0]["centroid_lon"], rows[0]["name"]
    elif lat is not None and lon is not None:
        center_name = f"{lat:.4f}, {lon:.4f}"
    else:
        return error("Give either municipality_ags or both lat and lon.")
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return error("lat/lon out of range.")
    if not (0 < radius_km <= MAX_RADIUS_KM):
        return error(f"radius_km must be between 0 and {MAX_RADIUS_KM}.")
    techs, err = check_technologies([technology] if technology else None)
    if err:
        return err
    limit = max(1, min(int(limit), 2000))
    r_m = radius_km * 1000

    cond = "u.status = 'in_operation' AND coalesce(u.net_capacity_kw, 0) >= %s"
    extra = [min_capacity_kw]
    if techs:
        cond += " AND u.technology = %s"
        extra.append(techs[0])
    pt = "ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography"

    agg = query(
        f"""SELECT count(*) n, coalesce(sum(u.net_capacity_kw), 0) kw FROM energy_energyunit u
            WHERE ST_DWithin(u.geom::geography, {pt}, %s) AND {cond}""",  # noqa: S608
        [lon, lat, r_m, *extra],
    )[0]
    pts = query(
        f"""SELECT u.mastr_id, u.technology, u.net_capacity_kw kw, u.lat, u.lon,
                   extract(year FROM u.commissioning_date)::int AS year, m.name AS municipality,
                   round((ST_Distance(u.geom::geography, {pt}) / 1000)::numeric, 2) AS km
            FROM energy_energyunit u LEFT JOIN energy_municipality m ON m.ags = u.municipality_id
            WHERE ST_DWithin(u.geom::geography, {pt}, %s) AND {cond}
            ORDER BY u.net_capacity_kw DESC NULLS LAST LIMIT %s""",  # noqa: S608
        [lon, lat, lon, lat, r_m, *extra, limit],
    )
    # The data gap: units in municipalities touching the circle that have no public coordinates.
    gap = query(
        f"""SELECT count(*) n FROM energy_energyunit u
            WHERE u.geom IS NULL AND {cond}
              AND u.municipality_id IN (SELECT ags FROM energy_municipality
                                        WHERE ST_DWithin(geom::geography, {pt}, %s))""",  # noqa: S608
        [*extra, lon, lat, r_m],
    )[0]["n"]

    top10 = [
        {"mastr_id": p["mastr_id"], "technology": p["technology"], "net_capacity_kw": p["kw"],
         "municipality": p["municipality"], "commissioned": p["year"], "distance_km": p["km"]}
        for p in pts[:10]
    ]  # fmt: skip
    content = {
        "center": center_name, "radius_km": radius_km, "technology": techs[0] if techs else "all",
        "status": "in_operation", "basis": "net capacity",
        "units_with_coordinates_found": agg["n"], "total_net_capacity_mw": mw(agg["kw"]),
        "largest_units": top10,
        "units_without_coordinates_in_nearby_municipalities": gap,
        "caveat": (
            "Only units with public coordinates can be located. "
            f"{fmt_int(gap)} further matching units in the surrounding municipalities have no published "
            "coordinates (mostly small rooftop solar), so the true total is higher."
        ),
    }  # fmt: skip
    if len(pts) < agg["n"]:
        content["map_shows"] = f"{len(pts)} largest of {agg['n']} units"

    feats = [
        geojson_feature(
            json.dumps({"type": "Point", "coordinates": [p["lon"], p["lat"]]}),
            {"technology": p["technology"], "capacity_kw": p["kw"], "year": p["year"],
             "municipality": p["municipality"], "mastr_id": p["mastr_id"]},
        ) for p in pts
    ]  # fmt: skip
    tech_label = techs[0] if techs else "units"
    display = [{
        "kind": "map_points", "title": f"{tech_label} within {radius_km:g} km of {center_name}",
        "geojson": feature_collection(feats), "circle": {"lat": lat, "lon": lon, "radius_km": radius_km},
    }]  # fmt: skip
    summary = f"Found {fmt_int(agg['n'])} {tech_label} within {radius_km:g} km of {center_name} ({mw(agg['kw'], 1)} MW)"
    return ToolResult(content, display, summary)
