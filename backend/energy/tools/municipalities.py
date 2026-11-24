from difflib import SequenceMatcher

from energy.textnorm import normalize_name

from .base import ToolResult, error
from .base import query as db_query


def find_municipality(query: str, limit: int = 5) -> ToolResult:
    """Fuzzy name lookup (umlaut-folded, ILIKE + pg_trgm similarity)."""
    q = normalize_name(query or "")
    if not q:
        return error("Empty search text.")
    limit = max(1, min(int(limit), 20))
    rows = db_query(
        """
        SELECT ags, name, district_ags, district_name, population, centroid_lat, centroid_lon,
               round(similarity(name_normalized, %s)::numeric, 3) AS score
        FROM energy_municipality
        WHERE name_normalized ILIKE %s OR similarity(name_normalized, %s) > 0.3
        ORDER BY (name_normalized = %s) DESC, (name_normalized ILIKE %s) DESC, score DESC, population DESC NULLS LAST
        LIMIT %s
        """,
        [q, f"%{q}%", q, q, f"{q}%", limit],
    )
    districts = _matching_districts(q)
    if not rows and not districts:
        return error(f"No municipality or district matching '{query}' found in the region.", suggestions=[])
    exact = [r for r in rows if normalize_name(r["name"]) == q]
    content = {
        "matches": rows,
        "districts": districts,
        "note": "Use `ags` (8 digits) as `area`; `district_ags` (5 digits) selects the whole district.",
    }
    if len(exact) > 1:
        content["ambiguous"] = True
    parts = [f"{r['name']} ({r['ags']})" for r in rows[:1]] + [
        f"district {d['district_name']} ({d['district_ags']})" for d in districts[:1]
    ]
    return ToolResult(
        content,
        [],
        f"Found {len(rows)} municipality and {len(districts)} district match(es) for '{query}': " + ", ".join(parts),
    )


def _matching_districts(q: str) -> list[dict]:
    """Districts (Landkreise / Stadtkreise) whose name matches. ~44 rows, so matching is done in Python."""
    rows = db_query(
        "SELECT district_ags, district_name, count(*) AS municipalities, sum(population) AS population "
        "FROM energy_municipality GROUP BY 1, 2"
    )
    out = []
    for r in rows:
        n = normalize_name(r["district_name"])
        score = 1.0 if n == q else 0.9 if q in n else SequenceMatcher(None, q, n).ratio()
        if score >= 0.8:
            out.append({**r, "score": round(score, 2)})
    return sorted(out, key=lambda d: -d["score"])[:3]
