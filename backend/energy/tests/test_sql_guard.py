import psycopg
import pytest

from energy.tools import call_tool, sql_guard
from energy.tools.sql_guard import GuardError, validate

ALLOWED = [
    "SELECT * FROM energy_municipality",
    "select name, population from energy_municipality where population > 1000 order by 2 desc",
    "SELECT technology, count(*), sum(net_capacity_kw) FROM energy_energyunit GROUP BY technology",
    "SELECT m.name, count(*) FROM energy_energyunit u JOIN energy_municipality m ON m.ags = u.municipality_id GROUP BY m.name",
    "WITH t AS (SELECT technology, count(*) c FROM energy_energyunit GROUP BY 1) SELECT * FROM t",
    "SELECT name, rank() OVER (ORDER BY population DESC) FROM energy_municipality",
    "SELECT round(avg(net_capacity_kw)::numeric, 2), extract(year FROM commissioning_date) FROM energy_energyunit GROUP BY 2",
    "SELECT name FROM energy_municipality WHERE similarity(name_normalized, 'freiburg') > 0.3",
    "SELECT count(*) FROM public.energy_energyunit WHERE ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(7.8, 48.0), 4326)::geography, 5000)",
    "SELECT name FROM energy_municipality /* a comment */ -- another\n",
    "SELECT name FROM energy_municipality WHERE ags IN (SELECT municipality_id FROM energy_energyunit)",
]
REJECTED = [
    ("", "empty"),
    ("INSERT INTO energy_municipality (ags) VALUES ('1')", "insert"),
    ("UPDATE energy_municipality SET name = 'x'", "update"),
    ("DELETE FROM energy_energyunit", "delete"),
    ("DROP TABLE energy_energyunit", "drop"),
    ("CREATE TABLE x (a int)", "create"),
    ("ALTER TABLE energy_energyunit ADD COLUMN x int", "alter"),
    ("TRUNCATE energy_energyunit", "truncate"),
    ("SELECT 1; SELECT 2", "two selects"),
    ("SELECT 1 -- hi\n; DROP TABLE energy_energyunit", "comment hides second statement"),
    ("SELECT 1; /* x */ DELETE FROM energy_energyunit", "block comment then DML"),
    ("WITH d AS (DELETE FROM energy_energyunit RETURNING *) SELECT * FROM d", "DML in CTE"),
    ("WITH i AS (INSERT INTO energy_municipality (ags) VALUES ('1') RETURNING *) SELECT * FROM i", "insert in CTE"),
    ("SELECT * INTO newtable FROM energy_energyunit", "select into"),
    ("SELECT * FROM energy_energyunit FOR UPDATE", "locking"),
    ("SELECT * FROM pg_user", "pg_ table"),
    ("SELECT * FROM pg_catalog.pg_class", "schema-qualified catalog"),
    ("SELECT * FROM information_schema.tables", "information_schema"),
    ("SELECT * FROM some_other_table", "unknown table"),
    ("SELECT * FROM energy_energyunit a JOIN pg_shadow b ON true", "disallowed table in join"),
    ("SELECT pg_read_file('/etc/passwd')", "pg_read_file"),
    ("SELECT pg_sleep(10)", "pg_sleep"),
    ("SELECT lo_import('/etc/passwd')", "lo_import"),
    ("SELECT * FROM dblink('host=x', 'select 1') AS t(a int)", "dblink"),
    ("SELECT current_setting('is_superuser')", "current_setting"),
    ("SELECT set_config('default_transaction_read_only', 'off', false)", "set_config"),
    ("SELECT version()", "version"),
    ("SELECT * FROM generate_series(1, 10)", "table function"),
    ("COPY energy_energyunit TO '/tmp/x'", "copy"),
    ("SET ROLE postgres", "set role"),
    ("EXPLAIN SELECT 1", "explain"),
    ("SELECT FROM WHERE", "syntax error"),
    ("SELECT " + "1," * 3000 + "1", "too long"),
]  # fmt: skip


@pytest.mark.parametrize("sql", ALLOWED)
def test_allowed_selects_pass(sql):
    assert validate(sql).upper().startswith("SELECT") or validate(sql).upper().startswith("WITH")


@pytest.mark.parametrize("sql,why", REJECTED, ids=[w for _, w in REJECTED])
def test_dangerous_or_invalid_sql_is_rejected(sql, why):
    with pytest.raises(GuardError):
        validate(sql)


def test_comment_text_never_reaches_the_database():
    # We execute the regenerated AST, so comments are gone.
    assert "--" not in validate("SELECT name FROM energy_municipality -- secret\n")


# ---- execution (needs the DB)
@pytest.mark.django_db
def test_runs_and_limits_rows():
    r, _ = call_tool("run_readonly_sql", {"query": "SELECT mastr_id FROM energy_energyunit"})
    assert r.ok and r.llm_content["row_count"] == 200 and r.display[0]["kind"] == "table"
    assert r.llm_content["truncated_for_llm"] is True  # only 50 rows go to the model


@pytest.mark.django_db
def test_row_cap_is_500():
    r, _ = call_tool("run_readonly_sql", {"query": "SELECT a.mastr_id FROM energy_energyunit a, energy_energyunit b"})
    assert r.llm_content["row_count"] == 500


@pytest.mark.django_db
def test_geometry_columns_are_stripped():
    r, _ = call_tool("run_readonly_sql", {"query": "SELECT * FROM energy_municipality"})
    assert "geom" not in r.llm_content["columns"] and "geom_simplified" not in r.llm_content["columns"]
    assert "Geometry columns removed" in r.llm_content["note_geometry"]
    r, _ = call_tool(
        "run_readonly_sql", {"query": "SELECT ST_Y(ST_PointOnSurface(geom)) AS y FROM energy_municipality LIMIT 1"}
    )
    assert r.ok and 47 < r.llm_content["rows"][0][0] < 49  # computed numbers are fine


@pytest.mark.django_db
def test_statement_timeout_is_enforced(monkeypatch):
    monkeypatch.setattr(sql_guard, "TIMEOUT", "50ms")
    q = "SELECT count(*) FROM energy_energyunit a, energy_energyunit b, energy_energyunit c, energy_energyunit d"
    r, _ = call_tool("run_readonly_sql", {"query": q})
    assert not r.ok and "time limit" in r.llm_content["error"]


@pytest.mark.django_db
def test_readonly_role_cannot_write_at_database_level():
    """Even if the app-level guard had a hole, the DB itself refuses writes (two layers)."""
    with psycopg.connect(sql_guard.readonly_dsn()) as conn:  # layer 1: role defaults to read-only
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            conn.execute("DELETE FROM energy_energyunit")
    with psycopg.connect(sql_guard.readonly_dsn(), autocommit=True) as conn:  # layer 2: no privilege
        conn.execute("SET default_transaction_read_only = off")
        for stmt in ("DELETE FROM energy_energyunit", "UPDATE energy_municipality SET name = 'x'",
                     "DROP TABLE energy_energyunit"):  # fmt: skip
            with pytest.raises((psycopg.errors.InsufficientPrivilege, psycopg.errors.UndefinedTable)):
                conn.execute(stmt)


@pytest.mark.django_db
def test_readonly_role_cannot_read_other_tables():
    with psycopg.connect(sql_guard.readonly_dsn()) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("SELECT * FROM energy_datameta")


@pytest.mark.django_db
def test_guard_error_is_returned_as_tool_error():
    r, _ = call_tool("run_readonly_sql", {"query": "DROP TABLE energy_energyunit"})
    assert not r.ok and "error" in r.llm_content
