"""Guarded read-only SQL: the fallback tool for questions the structured tools can't answer.

Defence in depth (every layer is unit-tested):
  1. Parse with sqlglot; exactly one statement, and it must be a SELECT.
  2. Walk the AST: no DML/DDL/INTO/locks/commands anywhere (also inside CTEs).
  3. Table allow-list (2 tables), function allow-list (not a deny-list).
  4. We execute the SQL *regenerated from the AST*, not the user's raw text, so comment
     tricks can't smuggle anything through.
  5. Wrapped as SELECT * FROM (...) q LIMIT 500.
  6. Runs as the `wattwhere_ro` role (SELECT-only grants, default read-only) inside a
     READ ONLY transaction with a 5 s statement_timeout.
  7. Geometry columns are stripped from results (they'd bloat the LLM context).
"""

from __future__ import annotations

from urllib.parse import quote, urlparse, urlunparse

import psycopg
import sqlglot
from django.conf import settings
from django.db import connection
from sqlglot import exp

from .base import ToolResult, error, jsonable

ALLOWED_TABLES = {"energy_municipality", "energy_energyunit"}
MAX_ROWS = 500
MAX_QUERY_CHARS = 4000
TIMEOUT = "5s"

ALLOWED_FUNCTIONS = {
    # aggregates
    "COUNT", "SUM", "AVG", "MIN", "MAX", "STDDEV", "VARIANCE", "MEDIAN",
    "PERCENTILE_CONT", "PERCENTILE_DISC", "QUANTILE", "ARRAY_AGG", "STRING_AGG", "GROUP_CONCAT",
    # scalar
    "ROUND", "ABS", "CEIL", "CEILING", "FLOOR", "SQRT", "POWER", "POW", "LN", "LOG", "EXP", "MOD",
    "COALESCE", "NULLIF", "GREATEST", "LEAST", "CAST", "TRY_CAST", "EXTRACT", "DATE_TRUNC",
    "LOWER", "UPPER", "LENGTH", "SUBSTRING", "TRIM", "CONCAT", "LEFT", "RIGHT", "REPLACE",
    "IF", "CASE", "TO_CHAR", "CURRENT_DATE", "CURRENT_TIMESTAMP", "NOW", "DATE_PART",
    # window
    "ROW_NUMBER", "RANK", "DENSE_RANK", "NTILE", "LAG", "LEAD", "FIRST_VALUE", "LAST_VALUE",
    # trigram / geo (pure computation, no I/O)
    "SIMILARITY", "ST_X", "ST_Y", "ST_AREA", "ST_DISTANCE", "ST_DWITHIN", "ST_MAKEPOINT",
    "ST_POINT", "ST_SETSRID", "ST_CENTROID", "ST_POINTONSURFACE", "ST_CONTAINS", "ST_WITHIN",
    "ST_INTERSECTS", "ST_LENGTH", "ST_ASTEXT",
    # helpers sqlglot may emit
    "ARRAY", "LIST", "TIMESTAMP", "DATE", "YEAR", "MONTH", "DAY",
}  # fmt: skip

# Anything of these node types anywhere in the tree is rejected.
FORBIDDEN_NODES = (
    exp.Insert, exp.Update, exp.Delete, exp.Merge, exp.Create, exp.Drop, exp.Alter,
    exp.Command, exp.Into, exp.Lock, exp.Copy, exp.Set, exp.Use, exp.TruncateTable,
    exp.Grant, exp.Revoke, exp.Transaction, exp.Commit, exp.Rollback, exp.Pragma,
    exp.Describe, exp.Show, exp.Analyze, exp.Kill, exp.Cache, exp.Uncache, exp.Refresh,
    exp.LoadData, exp.Attach, exp.Detach, exp.Execute,
)  # fmt: skip


class GuardError(ValueError):
    pass


def validate(sql: str) -> str:
    """Return the normalized, safe SELECT text, or raise GuardError with a helpful message."""
    if not sql or not sql.strip():
        raise GuardError("Empty query.")
    if len(sql) > MAX_QUERY_CHARS:
        raise GuardError(f"Query too long (max {MAX_QUERY_CHARS} characters).")
    try:
        statements = [s for s in sqlglot.parse(sql, dialect="postgres") if s is not None]
    except sqlglot.errors.SqlglotError as e:
        raise GuardError(f"Could not parse SQL: {str(e).splitlines()[0][:200]}") from e
    if len(statements) != 1:
        raise GuardError("Exactly one SELECT statement is allowed.")
    tree = statements[0]
    if not isinstance(tree, exp.Select):
        raise GuardError("Only a plain SELECT statement is allowed.")

    cte_names = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
    for node in tree.walk():
        if isinstance(node, FORBIDDEN_NODES):
            raise GuardError(f"Forbidden construct: {type(node).__name__}.")
        if isinstance(node, exp.Table):
            name = node.name.lower()
            if node.args.get("catalog") or (node.args.get("db") and node.args["db"].name.lower() != "public"):
                raise GuardError("Schema-qualified tables are not allowed.")
            # table-valued functions (e.g. FROM generate_series(...)) have no plain name
            if not isinstance(node.this, exp.Identifier):
                raise GuardError("Table-valued functions are not allowed.")
            if name not in ALLOWED_TABLES and name not in cte_names:
                raise GuardError(f"Table '{node.name}' is not allowed. Allowed: {sorted(ALLOWED_TABLES)}.")
        if isinstance(node, exp.Func):
            fname = (node.name if isinstance(node, exp.Anonymous) else node.sql_name()).upper()
            if fname not in ALLOWED_FUNCTIONS:
                raise GuardError(f"Function '{fname.lower()}' is not allowed.")
    # Execute what we parsed, not what was typed.
    return tree.sql(dialect="postgres")


def readonly_dsn() -> str:
    """READONLY_DATABASE_URL, pointed at whichever database Django currently uses
    (so tests, which run on test_<name>, query the test DB)."""
    u = urlparse(settings.READONLY_DATABASE_URL)
    dbname = connection.settings_dict["NAME"]
    return urlunparse(u._replace(path="/" + quote(dbname)))


_geom_oids: set[int] | None = None


def _geometry_oids(cur) -> set[int]:
    global _geom_oids
    if _geom_oids is None:
        cur.execute("SELECT oid FROM pg_type WHERE typname IN ('geometry', 'geography')")
        _geom_oids = {r[0] for r in cur.fetchall()}
    return _geom_oids


def execute(sql: str) -> tuple[list[str], list[list], list[str]]:
    """Run validated SQL as the read-only role. Returns (columns, rows, stripped_columns)."""
    wrapped = f"SELECT * FROM ({sql}) q LIMIT {MAX_ROWS}"
    with psycopg.connect(readonly_dsn(), connect_timeout=5) as conn:
        conn.read_only = True  # BEGIN READ ONLY
        with conn.cursor() as cur:
            cur.execute(f"SET LOCAL statement_timeout = '{TIMEOUT}'")
            geom = _geometry_oids(cur)
            cur.execute(wrapped)
            names = [d.name for d in cur.description]
            keep = [i for i, d in enumerate(cur.description) if d.type_code not in geom]
            rows = [[jsonable(r[i]) for i in keep] for r in cur.fetchall()]
            return [names[i] for i in keep], rows, [n for i, n in enumerate(names) if i not in keep]


DESCRIPTION = """Last-resort read-only SQL (PostgreSQL) for questions the other tools cannot answer. \
Prefer find_municipality, capacity_summary, rank_municipalities, units_near and capacity_timeseries.
Exactly one SELECT; max 500 rows; 5 s timeout; geometry columns are removed from results.
Tables:
- energy_municipality(ags text PK 8-digit key, name, name_normalized, district_ags 5-digit, district_name, \
population int, area_km2 float, centroid_lat, centroid_lon, geom, geom_simplified)
- energy_energyunit(mastr_id PK, technology in (solar|wind|biomass|hydro|storage), status_raw, \
status in (in_operation|planned|decommissioned|other), net_capacity_kw, gross_capacity_kw, \
storage_capacity_kwh (storage only), commissioning_date, decommissioning_date, municipality_id -> \
energy_municipality.ags, postcode, lat, lon (NULL for most solar units), solar_location_type \
(Gebäudesolaranlage|Freiflächensolaranlage|Steckerfertige Solaranlage...), geom)
Capacities are in kW. Default to net_capacity_kw and status='in_operation'."""


def run_readonly_sql(query: str) -> ToolResult:
    """Guarded SQL fallback tool."""
    try:
        safe = validate(query)
    except GuardError as e:
        return error(str(e))
    try:
        cols, rows, stripped = execute(safe)
    except psycopg.errors.QueryCanceled:
        return error(f"Query exceeded the {TIMEOUT} time limit. Simplify it or add filters.")
    except psycopg.Error as e:
        return error("Database rejected the query: " + str(e).splitlines()[0][:200])
    truncated = len(rows) >= MAX_ROWS
    llm_rows = rows[:50]
    content = {"columns": cols, "rows": llm_rows, "row_count": len(rows), "truncated_for_llm": len(rows) > 50}
    if truncated:
        content["note"] = f"Result capped at {MAX_ROWS} rows."
    if stripped:
        content["note_geometry"] = f"Geometry columns removed from result: {stripped}"
    display = [{"kind": "table", "title": "SQL result", "columns": cols, "rows": rows[:100]}]
    return ToolResult(content, display, f"SQL returned {len(rows):,} row(s)")
