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
    if not rows:
        return error(f"No municipality matching '{query}' found in the region.", suggestions=[])
    exact = [r for r in rows if normalize_name(r["name"]) == q]
    content = {
        "matches": rows,
        "note": "Use `ags` (8 digits) as `area`; `district_ags` (5 digits) selects the whole district.",
    }
    if len(exact) > 1:
        content["ambiguous"] = True
    return ToolResult(content, [], f"Found {len(rows)} match(es) for '{query}': {rows[0]['name']} ({rows[0]['ags']})")
