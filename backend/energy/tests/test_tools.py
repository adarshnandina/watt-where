"""Tool tests run against the SYNTHETIC seed data. Expected values are recomputed
independently in Python from the same generator, not copied from tool output."""

import pytest

from energy.management.commands.seed_sample import SAMPLE_MUNICIPALITIES, generate_units
from energy.textnorm import normalize_name
from energy.tools import REGISTRY, anthropic_tool_definitions, call_tool

pytestmark = pytest.mark.django_db

UNITS = generate_units()  # tuples: id, tech, status_raw, status, net, gross, kwh, comm, decomm, ags, plz, lat, lon, loc
FREIBURG = "08311000"
POP = {m[0]: m[4] for m in SAMPLE_MUNICIPALITIES}


def expected(ags=None, tech=None, status="in_operation"):
    sel = [u for u in UNITS if (ags is None or u[9] == ags) and (tech is None or u[1] == tech)
           and (status == "any" or u[3] == status)]  # fmt: skip
    return len(sel), sum(u[4] for u in sel)


def test_normalize_name():
    assert normalize_name("Tübingen") == normalize_name("Tuebingen") == normalize_name("tubingen")
    assert normalize_name("Groß  Gerau") == "gross gerau"


# ---- find_municipality
def test_find_exact_and_fuzzy():
    r, _ = call_tool("find_municipality", {"query": "freiburg"})
    assert r.ok and r.llm_content["matches"][0]["ags"] == FREIBURG
    r, _ = call_tool("find_municipality", {"query": "Freiburgg im Breisgau"})
    assert r.llm_content["matches"][0]["ags"] == FREIBURG


def test_find_not_found_and_empty():
    r, _ = call_tool("find_municipality", {"query": "Zzzzzzzz"})
    assert not r.ok and "error" in r.llm_content
    r, _ = call_tool("find_municipality", {"query": "  "})
    assert not r.ok


# ---- capacity_summary
def test_capacity_summary_municipality_and_units():
    n, kw = expected(FREIBURG, "solar")
    r, _ = call_tool("capacity_summary", {"area": FREIBURG, "technologies": ["solar"]})
    c = r.llm_content
    assert c["total_units"] == n
    assert c["total_net_capacity_kw"] == pytest.approx(kw, rel=1e-6)
    assert c["total_net_capacity_mw"] == pytest.approx(kw / 1000, abs=0.01)  # kW -> MW
    assert c["total_kw_per_inhabitant"] == pytest.approx(kw / POP[FREIBURG], abs=0.001)  # per-capita maths
    assert {d["kind"] for d in r.display} == {"table", "map_highlight"}


def test_capacity_summary_district_and_region():
    r, _ = call_tool("capacity_summary", {"area": "08315"})  # 3 sample municipalities
    n = sum(expected(a)[0] for a in ("08315001", "08315002", "08315003"))
    assert r.llm_content["total_units"] == n
    r, _ = call_tool("capacity_summary", {"area": "region", "status": "any"})
    assert r.llm_content["total_units"] == len(UNITS)
    assert r.llm_content["population"] == sum(POP.values())


def test_capacity_summary_storage_kwh():
    r, _ = call_tool("capacity_summary", {"area": "region", "technologies": ["storage"]})
    assert r.llm_content["by_technology"][0]["usable_storage_kwh"] > 0


def test_capacity_summary_date_filter_and_empty():
    r, _ = call_tool("capacity_summary", {"area": "region", "commissioned_from": "2030"})
    assert r.ok and r.llm_content["total_units"] == 0 and "note" in r.llm_content
    r, _ = call_tool(
        "capacity_summary", {"area": "region", "commissioned_from": "2015", "commissioned_to": "2019-12-31"}
    )
    n = len([u for u in UNITS if u[3] == "in_operation" and 2015 <= u[7].year <= 2019])
    assert r.llm_content["total_units"] == n


@pytest.mark.parametrize(
    "args",
    [
        {"area": "99999999"}, {"area": "banana"}, {"area": "region", "technologies": ["coal"]},
        {"area": "region", "status": "weird"}, {"area": "region", "commissioned_from": "20x5"},
        {},  # missing required argument
        {"area": "region", "bogus": 1},  # unknown argument
    ],
)  # fmt: skip
def test_capacity_summary_bad_input_returns_error_not_exception(args):
    r, _ = call_tool("capacity_summary", args)
    assert not r.ok and r.llm_content["error"]


# ---- rank_municipalities
def test_rank_total_mw_and_choropleth_covers_all():
    r, _ = call_tool("rank_municipalities", {"metric": "total_mw", "limit": 3})
    per = {a: expected(a)[1] / 1000 for a in POP}
    best = max(per, key=per.get)
    top = r.llm_content["top"]
    assert top[0]["ags"] == best and len(top) == 3
    assert top[0]["total_mw"] == pytest.approx(per[best], abs=0.1)
    choro = next(d for d in r.display if d["kind"] == "map_choropleth")
    assert len(choro["geojson"]["features"]) == len(POP)


def test_rank_per_capita_min_population_and_asc():
    r, _ = call_tool("rank_municipalities", {"metric": "kw_per_capita", "min_population": 10000})
    assert all(t["population"] >= 10000 for t in r.llm_content["top"])
    r, _ = call_tool("rank_municipalities", {"metric": "unit_count", "order": "asc", "limit": 1})
    counts = {a: expected(a)[0] for a in POP}
    assert r.llm_content["top"][0]["unit_count"] == min(counts.values())


def test_rank_district_scope_and_errors():
    r, _ = call_tool("rank_municipalities", {"metric": "unit_count", "district_ags": "08315"})
    assert {t["ags"][:5] for t in r.llm_content["top"]} == {"08315"}
    for bad in ({"metric": "bogus"}, {"metric": "unit_count", "district_ags": "abc"},
                {"metric": "unit_count", "technology": "coal"}):  # fmt: skip
        assert not call_tool("rank_municipalities", bad)[0].ok


# ---- units_near
def test_units_near_counts_and_caveat():
    r, _ = call_tool("units_near", {"municipality_ags": FREIBURG, "radius_km": 5, "technology": "solar"})
    c = r.llm_content
    assert r.ok and "caveat" in c
    # without-coordinates count must be a non-negative integer and at least those of Freiburg itself
    own = len([u for u in UNITS if u[9] == FREIBURG and u[1] == "solar" and u[3] == "in_operation" and u[11] is None])
    assert c["units_without_coordinates_in_nearby_municipalities"] >= own
    pts = r.display[0]
    assert pts["kind"] == "map_points" and pts["circle"]["radius_km"] == 5
    assert len(pts["geojson"]["features"]) == c["units_with_coordinates_found"]


def test_units_near_point_and_radius_monotonic():
    small, _ = call_tool("units_near", {"lat": 47.995, "lon": 7.85, "radius_km": 5})
    big, _ = call_tool("units_near", {"lat": 47.995, "lon": 7.85, "radius_km": 50})
    assert big.llm_content["units_with_coordinates_found"] >= small.llm_content["units_with_coordinates_found"]
    assert big.llm_content["units_with_coordinates_found"] > 0
    far, _ = call_tool("units_near", {"lat": 53.0, "lon": 10.0, "radius_km": 5})
    assert far.ok and far.llm_content["units_with_coordinates_found"] == 0  # empty result


@pytest.mark.parametrize(
    "args",
    [{}, {"lat": 47.9}, {"municipality_ags": "00000000"}, {"lat": 95, "lon": 7}, {"lat": 47, "lon": 7, "radius_km": 500},
     {"lat": 47, "lon": 7, "radius_km": 0}, {"lat": 47, "lon": 7, "technology": "coal"}],
)  # fmt: skip
def test_units_near_bad_input(args):
    assert not call_tool("units_near", args)[0].ok


# ---- capacity_timeseries
def test_timeseries_cumulative_accounts_for_decommissioning():
    r, _ = call_tool(
        "capacity_timeseries", {"area": "region", "technologies": ["solar"], "from_year": 2005, "to_year": 2024}
    )
    sel = [u for u in UNITS if u[1] == "solar" and u[3] in ("in_operation", "decommissioned")]

    def at(year):
        return sum(u[4] for u in sel if u[7].year <= year and not (u[8] and u[8].year <= year)) / 1000

    vals = r.display[0]["series"][0]["values"]
    assert vals[0] == pytest.approx(at(2005), abs=0.01)
    assert vals[-1] == pytest.approx(at(2024), abs=0.01)
    assert r.display[0]["kind"] == "chart_line" and r.display[0]["x"][0] == 2005


def test_timeseries_non_cumulative_sums_to_total_commissioned():
    r, _ = call_tool("capacity_timeseries", {"area": FREIBURG, "from_year": 2000, "to_year": 2030, "cumulative": False})
    total = sum(sum(s["values"]) for s in r.display[0]["series"])
    exp_total = sum(u[4] for u in UNITS if u[9] == FREIBURG and u[3] in ("in_operation", "decommissioned")) / 1000
    assert total == pytest.approx(exp_total, abs=0.05)


def test_timeseries_bad_input():
    assert not call_tool("capacity_timeseries", {"area": "region", "from_year": 2030, "to_year": 2010})[0].ok
    assert not call_tool("capacity_timeseries", {"area": "nope"})[0].ok


# ---- registry
def test_registry_has_all_six_tools_and_cache_marker():
    assert set(REGISTRY) == {"find_municipality", "capacity_summary", "rank_municipalities", "units_near",
                             "capacity_timeseries", "run_readonly_sql"}  # fmt: skip
    defs = anthropic_tool_definitions()
    assert defs[-1]["cache_control"] == {"type": "ephemeral"} and "cache_control" not in defs[0]


def test_unknown_tool_is_an_error_result():
    r, _ = call_tool("nope", {})
    assert not r.ok
