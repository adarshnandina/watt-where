"""The eval's own scoring logic must be right, or the scores are meaningless."""

import pytest

from eval.run_eval import number_matches, numbers_in, score


@pytest.mark.parametrize(
    "text,expected",
    [
        ("9,854 units", 9854),
        ("9.854 Einheiten", 9854),
        ("103.8 MW", 103.8),
        ("103,8 MW", 103.8),
        ("1.234,5 MW", 1234.5),
        ("1,234.5 MW", 1234.5),
    ],
)
def test_numbers_in_formats(text, expected):
    assert expected in numbers_in(text)


def test_exact_vs_relative_matching():
    assert number_matches(9854, "There are 9,854 units", exact=True)
    assert not number_matches(9854, "There are 9,900 units", exact=True)
    assert number_matches(103.83, "about 104 MW", exact=False)  # within 1%
    assert not number_matches(103.83, "about 110 MW", exact=False)
    assert number_matches(2500.0, "the largest has 2.5 MW", exact=False)  # kW <-> MW phrasing


def test_score_flags_missing_tool_number_and_caveat():
    q = {"expect_numbers": ["units"], "expected_tools": ["units_near"], "must_mention_any": [["coordinates"]]}
    ok = score(q, {"units": 23}, "Found 23 turbines (only units with coordinates).", ["units_near"])
    assert ok["passed"]
    bad = score(q, {"units": 23}, "Found 25 turbines.", [])
    assert not bad["passed"]
    assert {k for k, c in bad["checks"].items() if not c["ok"]} == {"number:units", "tools", "caveat:coordinates"}


def test_out_of_scope_must_decline_without_figures_or_tools():
    q = {"out_of_scope": True}
    assert score(q, {}, "I can only answer questions about energy units in Baden-Württemberg.", [])["passed"]
    assert not score(q, {}, "It will cost 25 ct per kWh.", [])["passed"]
    assert not score(q, {}, "Sorry, no data.", ["capacity_summary"])["passed"]


def test_language_and_names_checks():
    q = {"language": "de", "expect_names": "names"}
    de = "Die installierte Leistung ist hoch und die Zahl der Anlagen ist in Freiburg gestiegen. Müllheim im Markgräflerland."
    assert score(q, {"names": ["Müllheim im Markgräflerland"]}, de, [])["passed"]
    assert not score(q, {"names": ["Kehl"]}, de, [])["passed"]
    assert not score(q, {"names": []}, "The capacity is high and installed.", [])["passed"]
