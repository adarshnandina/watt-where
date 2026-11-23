# Build Log

Plain-language notes on what was built and why, one entry per phase.

## Phase 0: Preflight and scaffold
**Built:** git repo (local only, no remote), `.gitignore` (covers `.env`, `data/`, `node_modules/`, venvs, sqlite), `.env.example`, Makefile, `docs/` stubs, a `uv` backend project pinned to Python 3.12 with all backend dependencies, and a Vite + React + TypeScript frontend with leaflet, react-leaflet, recharts, react-markdown, remark-gfm, Tailwind v4, vitest and prettier.

**Decisions / deviations:**
- Python is pinned to 3.12 because some geo/data wheels don't support the system's 3.14 yet.
- `.claude/` is also git-ignored (local tooling config, not part of the project).
- Package versions are whatever resolved today (e.g. React 19, Vite 8, TypeScript 7). The spec said "React 18+", so 19 is fine.
- Docker CLI is installed but the daemon was not running at preflight time. Needed from Phase 1.

## Phase 1: Database and Django skeleton
**Built:** `docker-compose.yml` (PostGIS 16-3.4 on host port 5433, named volume, healthcheck), `db/init.sql` (extensions + `wattwhere_ro` role), the Django project (`config`, apps `energy` and `agent`), models, migrations, and an async `/api/health`.

**Decisions:**
- No GeoDjango. Migration `0002` adds the geometry columns, GIST indexes (plus a `geography` expression index so metre-based `ST_DWithin` can use an index) and a trigram GIN index for fuzzy place-name search with plain SQL. This keeps the project free of a system GDAL dependency.
- The read-only role is created in `init.sql` (roles are cluster-level), but `SELECT` grants happen in a migration because the tables don't exist when the init script runs. Setting `default_transaction_read_only=on` on the role gives a second DB-level barrier; verified an `INSERT` as `wattwhere_ro` fails.
- Extensions are also created in the migration, so the pytest test database gets them too.
- Added a small `DataMeta` key/value table (not in the spec) to hold the data snapshot date shown by `/api/health` and injected into the system prompt.
- `.env` is read by a 15-line loader in settings instead of adding `django-environ`.
- `/api/health` returns a generic error on failure instead of the exception text.

## Phase 2: Data ingestion
**Built:** `seed_sample` (200 synthetic units, 5 box-shaped municipalities, deterministic seed), `import_municipalities` (VG250-EW), `import_mastr` (open-mastr SQLite → Postgres via COPY), shared `energy/loading.py` and `energy/textnorm.py`. Full detail and the column mapping are in `docs/DATA.md`.

**Result:** 1,103 municipalities (11.24 M inhabitants), 1.53 M units (1.06 M solar). Sanity check: Freiburg has ~104 MW solar in operation, 4 wind turbines (18 MW). The MaStR import takes ~35 s.

**Decisions:**
- Inspected the real schema before writing the importer (spec rule 5). The first guesses (`Lage`, `SpeMastrNummer`) were wrong, so this paid off. Storage kWh lives in a separate table.
- Read the raw `Einheiten*` tables instead of the `*_extended` views: simpler and faster.
- Importers are idempotent: TRUNCATE + COPY inside one transaction. Geometry and derived values (area, centroid, simplified geometry, point) are computed in SQL, so there is no geometry code in Python beyond WKT.
- Municipality keys not found in VG250 2025 are stored as NULL rather than pointing at nothing (121 units).
- `GF=4` filter confirmed against the BKG code table shipped inside the download, not assumed.

**Deviations:** VG250 2025 has no `geo84` variant; used the UTM32 GeoPackage and reprojected. The MaStR download (~9 GB on disk, ~30 min) was approved by the user first.

**Note:** the real data replaced the sample rows in the dev DB. Tests will use their own test database seeded with `seed_sample`.

## Phase 3: Tool layer
**Built:** `energy/tools/` with six tools (`find_municipality`, `capacity_summary`, `rank_municipalities`, `units_near`, `capacity_timeseries`, `run_readonly_sql`), a registry (`REGISTRY`, `anthropic_tool_definitions()`, `call_tool()`), and `sql_guard.py`. 83 tests pass offline (`uv run pytest`), `ruff` is clean. `backend/scripts/sample_outputs.py` prints every tool's output on the real data.

**Key design decisions (interview material):**
- **`llm_content` vs `display`:** every tool returns a `ToolResult` with three parts. The model only gets the small `llm_content` (totals, top-N). Heavy payloads (a 2 MB choropleth for all 1,103 municipalities, point layers, tables) go to `display` and straight to the browser. That saves tokens and latency and stops the model from re-typing numbers from a giant table.
- **Errors are data:** bad input (unknown area, bad technology, wrong date) comes back as `{"error": ..., "allowed": [...]}` so the model can fix its next call. `call_tool` validates arguments against the JSON schema first and never raises.
- **One registry, two front doors:** the same `REGISTRY` will feed the agent loop and the MCP server.
- **SQL guard in seven layers:** sqlglot parse (exactly one SELECT), AST walk rejecting DML/DDL/INTO/locks/commands anywhere (incl. inside CTEs), table allow-list, *function allow-list* (not deny-list), execution of the SQL *regenerated from the AST* so comments can't smuggle anything, `LIMIT 500` wrapper, and execution as the `wattwhere_ro` role in a READ ONLY transaction with a 5 s timeout. Geometry columns are stripped by type OID. Tests cover 33 rejected and 11 allowed queries, the timeout, and DB-level write refusal (two separate layers).
- Cumulative time series is computed as two small aggregates (added per year, removed per year) plus a running sum in Python, instead of a years × units cross join, which would be slow on 1.5 M rows.
- The coordinate caveat is built into `units_near`: the result carries the number of matching units in the nearby municipalities that have no coordinates.

**Real-data sanity check (Freiburg im Breisgau, 08311000, units in operation, net):**
| Check | Result |
|---|---|
| All technologies | 14,019 units, 155.6 MW (0.65 kW/inhabitant) |
| Solar | 9,854 units, 103.8 MW |
| Storage | 4,138 units, 25.5 MW, 40.6 MWh usable |
| Wind | 4 units, 18.3 MW |
| Wind within 25 km of Freiburg | 23 turbines, 57.6 MW |
| Breisgau-Hochschwarzwald district | 42,648 units, 500.6 MW |
| BW wind total | 950 units, 2,337 MW (plausible for 2026) |
| Top solar kW/capita (pop ≥ 1,000) | Langenenslingen 25.4, Külsheim 25.0 (large ground-mounted parks) |

**Notes / deviations:**
- The sandbox test DB needs the sample data *committed* (a `conftest.py` session fixture) because the SQL tool uses a second connection as the read-only role, and that connection can't see uncommitted rows.
- sqlglot names some functions differently from Postgres (`ST_MakePoint` is `ST_POINT`); the allow-list uses sqlglot's names. A test caught this.
- The region-wide choropleth is ~2 MB of GeoJSON (4 decimal places). Fine for a one-off SSE event; could be trimmed later if needed.
