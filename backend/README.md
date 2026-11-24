# WattWhere backend

Django 5.2 (ASGI, served by uvicorn) on PostgreSQL 16 + PostGIS. Python 3.12, managed with [uv](https://docs.astral.sh/uv/).

## Run

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py seed_sample                    # synthetic sample data
uv run uvicorn config.asgi:application --reload --port 8000
uv run pytest                                          # offline: no API key, no network (needs the DB container)
uv run ruff check . && uv run ruff format --check .
```

Or use the root `Makefile` (`make migrate`, `make dev-backend`, `make test`, ...). Configuration comes from the repository's `.env` (see the root README).

## Layout

| Path | Purpose |
|---|---|
| `config/` | Django settings (env-driven), URLs, ASGI app |
| `energy/models.py`, `migrations/` | `Municipality`, `EnergyUnit`, `DataMeta`; PostGIS columns, indexes and the read-only role grants are in a `RunSQL` migration |
| `energy/management/commands/` | `seed_sample`, `import_municipalities` (BKG VG250-EW), `import_mastr` (open-mastr export) |
| `energy/loading.py` | Idempotent bulk loaders (truncate + COPY in one transaction) |
| `energy/tools/` | **The tool layer**: `find_municipality`, `capacity_summary`, `rank_municipalities`, `units_near`, `capacity_timeseries`, guarded `run_readonly_sql`; `__init__.py` is the registry |
| `agent/` | `loop.py` (Claude streaming + tool loop), `events.py` (SSE protocol), `prompts.py`, `views.py` (`/api/chat`, `/api/examples`, municipality search) |
| `energy/views.py` | `/api/health` (DB check, data snapshot, row counts) |
| `mcp_server/` | MCP server over stdio, built from the same registry |
| `eval/` | 25-question evaluation: `questions.yaml`, `ground_truth.py` (independent SQL), `run_eval.py`, stored runs in `results/` |
| `scripts/sample_outputs.py` | Prints every tool's output for Freiburg on the real data |

## Adding a tool

1. Write a function in `energy/tools/` that validates its input and returns a `ToolResult(llm_content, display, summary)`. Return errors as data (`error(...)`), never raise. Use parameterized SQL only.
2. Register it in `energy/tools/__init__.py` with a description and a JSON schema.
3. Add tests (happy path, empty result, bad input). The web agent and the MCP server pick it up automatically.

Keep `llm_content` small (totals, top-N); put large payloads in `display`.

## Tests

`pytest-django` creates a test database from the migrations and loads the synthetic sample once (committed, because the guarded SQL tool uses a second connection as the read-only role). Agent tests use a scripted fake Anthropic client. The evaluation is separate (`make eval`) because it needs real data and an API key.

## Notes

- The SQL guard is the security-sensitive part: see `energy/tools/sql_guard.py` and its tests before changing it.
- Logs: one JSON line per chat request on stdout (question, tools, durations, token usage). The API key is never logged.
