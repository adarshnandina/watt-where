# WattWhere: Build Specification for Claude Code

> **Read this whole file before you start.** It is the complete brief for building the project. Work through the phases in order and check each phase's acceptance criteria before you move on.

---

## 0. Hard rules (read first)

1. **Never push anything to GitHub or any other remote.**
   - Do not run `git push`, `git remote add`, `gh repo create`, or any other `gh` command.
   - Do not create a remote repository of any kind.
   - You **may** run `git init` and make **local** commits at the end of each phase as checkpoints. If you're unsure, don't commit and leave git to the user.
2. **Never commit secrets.** `ANTHROPIC_API_KEY` lives only in `.env`, which must be listed in `.gitignore` before the first commit. Commit a `.env.example` with placeholder values instead.
3. **Never commit data.** Raw downloads, SQLite files, shapefiles and database dumps all go in `data/`, which is git-ignored, except for small test fixtures under `backend/energy/tests/fixtures/`.
4. **Ask the user before any download larger than 500 MB.** The MaStR bulk export is several GB (see Phase 2). Tell the user the size and the expected time, then wait for a yes.
5. **Don't guess data schemas.** Inspect the real tables and columns first (Phase 2), write down what you find in `docs/DATA.md`, and only then write code that depends on them.
6. **Keep a build log.** After each phase, append a short entry to `docs/BUILD_LOG.md`: what was built, the key design decisions and why, and anything you deviated from in this spec. The user will use this file to prepare for interviews, so explain decisions in plain language.
7. **If you're blocked** (a dependency won't install, a URL has moved, a data column is missing), try a reasonable fix. If that doesn't work, stop and explain the problem to the user. Don't silently drop a feature.

---

## 1. What we're building and why

**WattWhere** is a web app for asking natural-language questions about the energy transition in **Baden-Württemberg** (focus area: Freiburg im Breisgau). Answers stream back in a chat interface, and the results also appear on an interactive map and in charts.

Example questions it must handle:

- "How much solar capacity is installed in Freiburg im Breisgau?"
- "Which 10 municipalities in Baden-Württemberg have the most solar capacity per inhabitant?"
- "Show me wind turbines within 25 km of Freiburg."
- "How has battery storage capacity in Freiburg grown since 2015?"
- "Compare solar and wind capacity in the Breisgau-Hochschwarzwald district."

**Purpose:** This is a portfolio project for a working-student application at **greenventory GmbH** (Freiburg). Their role asks for:

- React frontends with AI features at their core: chat interfaces, streaming responses and agent-style workflows
- Connecting applications to LLMs and to their own data via APIs and **MCP servers**
- Making **geospatial and energy datasets** accessible through **natural-language querying**
- Python, **Django**, REST APIs and databases

The project must demonstrate all of these. The user's background is strong in Python, LLMs/RAG and agents, but **new to React**, so write clean, idiomatic, well-commented React that he can read and explain.

---

## 2. Tech stack (use exactly this unless blocked)

| Layer | Choice |
|---|---|
| Python | 3.12, pinned with `uv python pin 3.12` (the user's machine has 3.14; some geo/data dependencies may not support it yet) |
| Python package manager | `uv` (already installed on the user's Mac) |
| Backend | Django 5.2 LTS, run under **ASGI** with `uvicorn` (async views are needed for streaming) |
| REST | Plain Django views returning `JsonResponse`, plus one streaming endpoint. Don't add Django REST Framework unless it's clearly needed. |
| Database | PostgreSQL 16 + **PostGIS** in Docker (`postgis/postgis:16-3.4` image), exposed on host port **5433** |
| DB driver | `psycopg[binary]` 3 |
| Geo processing (import only) | `geopandas` + `pyogrio` (wheels bundle GDAL; no system GDAL needed). **Do not use GeoDjango**: add the PostGIS geometry columns with `RunSQL` migrations and query them with raw SQL. |
| Energy data | `open-mastr` Python package (Marktstammdatenregister bulk export) |
| LLM | Anthropic Python SDK (`anthropic`), async client, **streaming + tool use**. Read the model from env var `ANTHROPIC_MODEL`, default `claude-sonnet-5-5` (the user can switch to `claude-haiku-5-5` for cheaper development). |
| SQL safety | `sqlglot` for parsing and validating the guarded SQL tool |
| MCP | Official `mcp` Python SDK (`FastMCP`), stdio transport |
| Frontend | Vite + React 18+ + **TypeScript** |
| Map | `leaflet` + `react-leaflet`, OpenStreetMap raster tiles with proper attribution |
| Charts | `recharts` |
| Markdown in chat | `react-markdown` + `remark-gfm` |
| Styling | Tailwind CSS v4 (`@tailwindcss/vite`). Keep it clean and simple. |
| Tests | `pytest` + `pytest-django` + `pytest-asyncio` (backend); `vitest` (frontend) |
| Lint/format | `ruff` (Python), `eslint` + `prettier` (TS) |

Preflight checks: Docker, Node ≥ 20 and `uv` must be available. If something is missing, tell the user exactly what to install. Don't install system-level tools yourself.

---

## 3. Repository layout

```
wattwhere/
├── .env.example
├── .gitignore
├── Makefile
├── README.md
├── docker-compose.yml
├── docs/
│   ├── ARCHITECTURE.md
│   ├── BUILD_LOG.md
│   ├── DATA.md
│   └── EVAL.md
├── data/                       # git-ignored: downloads, shapefiles, sqlite
├── backend/
│   ├── pyproject.toml          # uv project
│   ├── manage.py
│   ├── config/                 # Django project: settings.py, urls.py, asgi.py
│   ├── energy/                 # Django app: models, importers, tools
│   │   ├── models.py
│   │   ├── migrations/
│   │   ├── management/commands/
│   │   │   ├── import_municipalities.py
│   │   │   ├── import_mastr.py
│   │   │   └── seed_sample.py
│   │   ├── tools/              # the tool layer; single source of truth
│   │   │   ├── __init__.py     # registry: name → (fn, json_schema, description)
│   │   │   ├── municipalities.py
│   │   │   ├── capacity.py
│   │   │   ├── spatial.py
│   │   │   ├── timeseries.py
│   │   │   └── sql_guard.py
│   │   └── tests/
│   ├── agent/                  # Django app: LLM loop + streaming endpoint
│   │   ├── prompts.py
│   │   ├── loop.py
│   │   ├── events.py
│   │   ├── views.py
│   │   └── tests/
│   ├── mcp_server/
│   │   └── server.py
│   └── eval/
│       ├── questions.yaml
│       └── run_eval.py
└── frontend/
    ├── package.json
    ├── vite.config.ts          # proxies /api → http://localhost:8000
    ├── index.html
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── api/
        │   ├── sse.ts          # POST-based SSE stream parser
        │   └── types.ts        # event types (mirror backend/agent/events.py)
        ├── hooks/
        │   └── useChat.ts
        ├── components/
        │   ├── ChatPanel.tsx
        │   ├── MessageList.tsx
        │   ├── Message.tsx
        │   ├── ToolCallChip.tsx
        │   ├── Composer.tsx
        │   ├── ExampleQuestions.tsx
        │   ├── MapView.tsx
        │   ├── ChartCard.tsx
        │   └── ResultTable.tsx
        └── test/
```

---

## 4. Data

### 4.1 Sources and licences

| Dataset | What it gives us | Licence / attribution |
|---|---|---|
| **Marktstammdatenregister (MaStR)**, via `open-mastr` bulk download | Every registered generation and storage unit in Germany: technology, capacity, status, commissioning date, municipality key, postcode, and coordinates where published | Bundesnetzagentur, dl-de/by-2-0. Show "Datenquelle: Marktstammdatenregister (Bundesnetzagentur), dl-de/by-2-0" in the UI footer. |
| **BKG VG250-EW** (administrative areas 1:250 000 **with population**, as of 31.12) | Municipality (Gemeinde) boundaries, official municipality key (AGS/ARS), population (`EWZ`) | © BKG (year) dl-de/by-2-0. Show it in the UI footer. |

### 4.2 Getting VG250-EW

- Download from the BKG open-data server `https://daten.gdz.bkg.bund.de/produkte/vg/`. Look for the latest `vg250-ew_ebenen_1231/<year>/` folder and prefer the **WGS84 (`geo84`)** or **GeoPackage** variant.
- The exact file names change between years, so list the directory and pick the newest available. If you can't find it, ask the user to download it manually and tell them where to put it (`data/vg250/`).
- Use the **Gemeinden** layer (`VG250_GEM`). Keep only Baden-Württemberg: the AGS starts with `08`. Make the Bundesland configurable via the env var `REGION_LAND_PREFIX`, default `08`.
- Keep the fields AGS (8-digit municipality key), the name (`GEN`), the district from the first 5 AGS digits, and the population `EWZ`. Look up district names from the `VG250_KRS` layer.
- If the data has multiple rows per AGS (e.g. `GF` geofactor variants), keep only land areas (`GF = 4` in VG250 conventions). **Verify this against the BKG documentation shipped in the download and record what you did in `docs/DATA.md`.**
- Reproject to EPSG:4326 if needed. Store **two geometries**: the full one, and a simplified one for the map (`ST_SimplifyPreserveTopology`, tolerance ~0.0005°). Also store a centroid (point-on-surface) lat/lon.

### 4.3 Getting MaStR

```python
from open_mastr import Mastr
db = Mastr()  # creates SQLite under $HOME/.open-MaStR/data/sqlite/ (override with SQLITE_DATABASE_PATH / OUTPUT_PATH)
db.download(data=["solar", "wind", "biomass", "hydro", "storage"])
```

- The bulk download fetches the **full national export zip (several GB)**, even when you pass `data=[...]`. **Ask the user before starting it** (rule 4). Set `OUTPUT_PATH` so everything lands in `data/open-mastr/` inside the repo instead of the home folder.
- After the download, **inspect the SQLite schema** (`.tables`, `PRAGMA table_info(...)`) and record in `docs/DATA.md` the exact table and column names you use. The table names (e.g. `solar_extended` vs `units_solar`) and column spellings depend on the `open-mastr` version. Columns you'll need, under whatever names they have:
  - unit id (MaStR-Nr, `EinheitMastrNummer`)
  - operating status (`EinheitBetriebsstatus`; keep the raw value, and also map it to `in_operation` / `planned` / `decommissioned` / `other`)
  - gross and net capacity in kW (`Bruttoleistung`, `Nettonennleistung`)
  - commissioning date (`Inbetriebnahmedatum`) and decommissioning date if present
  - Bundesland, municipality key (`Gemeindeschluessel`), municipality name, postcode (`Postleitzahl`)
  - latitude/longitude (`Breitengrad`, `Laengengrad`)
  - for solar: location type if present (e.g. building vs ground-mounted, `Lage`)
  - for storage: usable storage capacity in kWh, if it's in the table
- **Important data caveat:** many small units (especially rooftop solar) **do not have public coordinates**, for privacy reasons. Count how many units have coordinates and record it in `docs/DATA.md`. The app must aggregate by municipality (which nearly all units have) and show only units with coordinates as map points. The agent must mention this caveat when a point-based answer could be incomplete.
- Filter to the region (Bundesland = Baden-Württemberg, or AGS prefix `08`).
- Report row counts per technology after the import. Sanity check: Baden-Württemberg should have **hundreds of thousands** of solar units. If you get a few hundred, something is wrong.

### 4.4 Database schema (Django models in `energy/models.py`)

```python
class Municipality(models.Model):
    ags = models.CharField(max_length=8, primary_key=True)   # official 8-digit key
    name = models.CharField(max_length=200, db_index=True)
    name_normalized = models.CharField(max_length=200, db_index=True)  # lowercase, umlauts folded, for fuzzy lookup
    district_ags = models.CharField(max_length=5, db_index=True)
    district_name = models.CharField(max_length=200)
    population = models.IntegerField(null=True)
    area_km2 = models.FloatField(null=True)
    centroid_lat = models.FloatField()
    centroid_lon = models.FloatField()
    # geometry columns added via RunSQL migration (not mapped by Django):
    #   geom geometry(MultiPolygon, 4326), geom_simplified geometry(MultiPolygon, 4326)
    #   + GIST index on geom

class EnergyUnit(models.Model):
    mastr_id = models.CharField(max_length=32, primary_key=True)
    technology = models.CharField(max_length=20, db_index=True)  # solar|wind|biomass|hydro|storage
    status_raw = models.CharField(max_length=100)
    status = models.CharField(max_length=20, db_index=True)      # in_operation|planned|decommissioned|other
    net_capacity_kw = models.FloatField(null=True)
    gross_capacity_kw = models.FloatField(null=True)
    storage_capacity_kwh = models.FloatField(null=True)
    commissioning_date = models.DateField(null=True, db_index=True)
    decommissioning_date = models.DateField(null=True)
    municipality = models.ForeignKey(Municipality, null=True, on_delete=models.SET_NULL, db_constraint=False)
    postcode = models.CharField(max_length=5, null=True)
    lat = models.FloatField(null=True)
    lon = models.FloatField(null=True)
    solar_location_type = models.CharField(max_length=100, null=True)
    # geometry column added via RunSQL: geom geometry(Point, 4326) (null when no coordinates) + GIST index
```

- Add sensible composite indexes, e.g. `(municipality, technology, status)`.
- Bulk-load with `COPY` or `executemany` in batches, not row-by-row ORM saves. The import should take minutes, not hours.
- Make importers **idempotent**: re-running replaces the data (truncate and load inside a transaction).
- Create a **read-only Postgres role** `wattwhere_ro` with `SELECT` only on `energy_municipality` and `energy_energyunit`. The guarded SQL tool connects as this role (see 5.6). Create it in a migration or an init SQL script mounted into the Docker container.

### 4.5 Sample data for development and tests

`python manage.py seed_sample` loads a **small, deterministic fixture**: about 5 municipalities around Freiburg with simple polygon geometries and about 200 synthetic units. Mark it clearly as synthetic in code comments and in the README. Tests use this fixture only. They must never need the real download or a network connection.

---

## 5. Tool layer (`backend/energy/tools/`)

This is the core of the project. **One set of Python functions** is used both by the in-app agent and by the MCP server. Each tool:

- Is a plain function with typed arguments that returns a `ToolResult` dataclass:
  ```python
  @dataclass
  class ToolResult:
      llm_content: dict        # compact, summarized data sent back to the LLM (keep it small: top-N rows, totals)
      display: list[dict]      # UI payloads (map layers, charts, tables) sent ONLY to the frontend
      summary: str             # one-line human summary for the tool-call chip, e.g. "Found 1,102 solar units in Freiburg"
  ```
  **Design point worth explaining in BUILD_LOG:** big payloads (GeoJSON, full tables) go straight to the UI and never enter the LLM context. The model sees compact numbers, which keeps cost and latency down and reduces hallucination.
- Has a JSON schema and a clear description, registered in `tools/__init__.py`.
- Validates its inputs and returns helpful errors as data (e.g. `{"error": "Municipality 'Freiberg' not found", "suggestions": ["Freiburg im Breisgau", ...]}`) instead of raising.
- Uses parameterized SQL only. Never interpolate strings into SQL.
- Reports capacity in **kW in data and MW in summaries**, and states clearly whether figures are net or gross (default: **net capacity, units in operation**).

### 5.1 `find_municipality(query: str, limit: int = 5)`
Fuzzy lookup by name (normalize umlauts/ß, use `ILIKE` and trigram similarity via the `pg_trgm` extension). Returns AGS, name, district, population and centroid. Display: none.

### 5.2 `capacity_summary(area: str, technologies: list[str] | None, status: str = "in_operation", commissioned_from: str | None, commissioned_to: str | None)`
`area` is a municipality AGS (8 digits), a district AGS (5 digits) or `"region"` (the whole Bundesland). Returns unit count, total net capacity (MW), capacity per inhabitant (kW/inhabitant) and storage kWh where relevant, broken down by technology. Display: a small table, plus a map layer highlighting the area polygon(s).

### 5.3 `rank_municipalities(metric: "total_mw" | "kw_per_capita" | "unit_count" | "mw_per_km2", technology: str | None, district_ags: str | None, order: "desc" | "asc" = "desc", limit: int = 10, min_population: int = 0)`
Returns the top-N list to the LLM. Display: a **choropleth map layer** covering *all* municipalities in scope (`geom_simplified` as GeoJSON with the metric value in properties), plus a table of the top N. Support `min_population` so per-capita rankings aren't dominated by tiny villages, and have the agent mention this.

### 5.4 `units_near(lat: float | None, lon: float | None, municipality_ags: str | None, radius_km: float = 10, technology: str | None, min_capacity_kw: float = 0, limit: int = 500)`
PostGIS `ST_DWithin` on `geography`. Only units **with coordinates**. Returns the count, total MW and the 10 largest units to the LLM, and always includes how many units in the searched municipalities lack coordinates (the caveat). Display: a **points layer** (GeoJSON, properties: technology, capacity, commissioning year) and a radius circle.

### 5.5 `capacity_timeseries(area: str, technologies: list[str] | None, from_year: int = 2000, to_year: int | None, cumulative: bool = True)`
Capacity commissioned per year, optionally cumulative. Account for decommissioning dates when cumulative. Display: a **line chart** (one series per technology).

### 5.6 `run_readonly_sql(query: str)` (guarded fallback)
For questions the structured tools can't answer. Guards, **all of which must be unit-tested**:
- Parse with `sqlglot` (Postgres dialect). Reject anything that isn't exactly **one `SELECT` statement**. That includes CTEs that contain DML, `INTO`, multiple statements and comments hiding statements.
- Allow only the tables `energy_municipality` and `energy_energyunit`. Reject `pg_*`, `information_schema`, functions such as `pg_read_file`, `dblink`, `lo_*`, etc. Use an allow-list of functions, not a deny-list.
- Wrap the query as `SELECT * FROM (<query>) q LIMIT 500`.
- Execute as the `wattwhere_ro` role, in a read-only transaction, with `SET LOCAL statement_timeout = '5s'`.
- Never return geometry columns to the LLM. Strip them or convert them to centroids.
- Display: a table.

The system prompt tells the model to **prefer the structured tools** and use SQL only as a last resort. Include the table schema (column names, units and meanings) in the tool description.

---

## 6. Agent and streaming API (`backend/agent/`)

### 6.1 Endpoint

`POST /api/chat`. Request body:
```json
{ "messages": [ {"role": "user", "content": "..."}, {"role": "assistant", "content": "..."} ] }
```
The backend is stateless: the client sends the visible text history. The backend rebuilds the conversation for the LLM (prior tool calls aren't replayed, which is fine; note this in BUILD_LOG as a deliberate simplification).

Response: `Content-Type: text/event-stream`, implemented as an **async Django view** returning `StreamingHttpResponse` over an async generator, served by uvicorn. Set `Cache-Control: no-cache` and `X-Accel-Buffering: no`. Send a comment heartbeat (`: ping`) every 15 s during long tool calls.

Other endpoints:
- `GET /api/health`: checks the DB connection and returns data freshness (MaStR export date, row counts).
- `GET /api/examples`: returns the example questions.
- `GET /api/municipalities/search?q=`: used by the frontend autocomplete (optional; nice to have).

### 6.2 Event protocol (define it once in `agent/events.py`, mirror it in `frontend/src/api/types.ts`)

Each SSE message is `event: <type>\ndata: <json>\n\n`.

| `type` | `data` | When |
|---|---|---|
| `message_start` | `{ "id": str }` | Once, at the start |
| `text_delta` | `{ "text": str }` | Each streamed token chunk from the model |
| `tool_call` | `{ "id": str, "name": str, "input": object }` | When the model calls a tool (before execution) |
| `tool_result` | `{ "id": str, "name": str, "summary": str, "ok": bool, "duration_ms": int }` | After the tool runs |
| `display` | `{ "tool_call_id": str, "payload": DisplayPayload }` | For each display item a tool produced |
| `error` | `{ "message": str, "retryable": bool }` | On failure (never leak stack traces or keys) |
| `message_end` | `{ "usage": {input_tokens, output_tokens, cache_read_input_tokens?}, "stop_reason": str }` | Once, at the end |

`DisplayPayload` is a discriminated union:
```ts
type DisplayPayload =
  | { kind: "map_choropleth"; title: string; unit: string; geojson: FeatureCollection /* props: ags, name, value */ }
  | { kind: "map_points";     title: string; geojson: FeatureCollection; circle?: { lat: number; lon: number; radius_km: number } }
  | { kind: "map_highlight";  title: string; geojson: FeatureCollection }
  | { kind: "chart_line";     title: string; x: (string|number)[]; series: { name: string; values: number[] }[]; y_unit: string }
  | { kind: "table";          title: string; columns: string[]; rows: (string|number|null)[][] };
```

### 6.3 Agent loop (`agent/loop.py`)

- Use `anthropic.AsyncAnthropic().messages.stream(...)` with the tool definitions from the registry.
- Forward text deltas as `text_delta` events as they arrive.
- When `stop_reason == "tool_use"`: emit `tool_call`, run the tool (the DB code is sync, so wrap it in `sync_to_async`), emit `tool_result` and `display` events, append `tool_result` blocks with `llm_content` (JSON) to the conversation, and continue.
- Allow at most **8 tool rounds** per user message. If the limit is hit, stop gracefully with a message.
- Run independent tool calls from the same turn concurrently (`asyncio.gather`).
- Use **prompt caching**: put `cache_control: {"type": "ephemeral"}` on the system prompt and the last tool definition. Log cache hits from `usage`.
- Handle client disconnects: if the request is cancelled, stop the LLM stream and don't run further tools.
- Handle Anthropic API errors (rate limit, overload) with one retry and backoff, then emit `error`.
- Log every request (question, tools called, durations, tokens) as structured JSON to stdout. Never log the API key.

### 6.4 System prompt (`agent/prompts.py`)

Write a clear system prompt that:
- States the scope: energy units and municipalities in the configured region (Baden-Württemberg), from MaStR and BKG data, as of the data snapshot date (inject this from the DB).
- Tells the model to **always use tools to get numbers and never state figures from its own knowledge**, to resolve place names with `find_municipality` first, and to prefer structured tools over SQL.
- Sets the defaults: net capacity, units in operation, MW for totals. The answer must state these assumptions briefly.
- Requires the coordinate caveat whenever point data is involved.
- Tells it to keep answers short (2–5 sentences plus a few bullets if needed), because the map, chart and table carry the detail, and to refer to them ("see the map").
- Answers in the language of the question (German or English).
- Politely declines questions outside the dataset and says what it *can* answer.

---

## 7. Frontend (`frontend/`)

### 7.1 Layout

Desktop-first, responsive enough not to break on a laptop:
- **Left (~40%)**: chat panel. Header with the app name and a one-line description; message list; composer at the bottom.
- **Right (~60%)**: map, full height. Below it, or as an overlay card, the latest chart and table, collapsible.
- **Footer**: data attributions (MaStR / BKG / OSM) and the data snapshot date from `/api/health`.
- **Empty state**: 4–6 clickable example questions (from `/api/examples`).

### 7.2 Streaming client (`src/api/sse.ts`)

- `EventSource` can't POST, so use `fetch` + `response.body.getReader()` + `TextDecoder` and parse SSE frames manually (handle frames split across chunks, multiple frames per chunk, comment lines and `event:`/`data:` fields).
- Expose it as an async generator: `async function* streamChat(messages, signal): AsyncGenerator<ChatEvent>`.
- **Unit-test the parser with vitest**, including split-chunk edge cases.

### 7.3 State (`src/hooks/useChat.ts`)

A `useReducer`-based hook that holds the messages. Each assistant message has its text, a list of tool calls with their status (pending / ok / error) and summaries, and its display payloads. It exposes `send(text)`, `stop()` (aborts with `AbortController`), `isStreaming` and `error`. Write extensive comments explaining *why* each piece exists, because the user is learning React.

### 7.4 Components

- **Message**: renders streaming markdown (`react-markdown` + `remark-gfm`). Shows a blinking cursor while streaming.
- **ToolCallChip**: an inline chip per tool call, e.g. "🔎 capacity_summary: Found 1,102 solar units in Freiburg (240 ms)". A spinner while pending, red on error, expandable to show the input JSON. This is the visible "agent-style workflow."
- **Composer**: textarea; Enter sends, Shift+Enter adds a newline; disabled while streaming, with a **Stop** button.
- **MapView**: react-leaflet map centred on Freiburg (47.995, 7.85), zoom 9. It renders the most recent map payload(s):
  - choropleth: a sequential colour scale (5–7 quantile classes), a legend with the unit, and a hover tooltip with the name and value
  - points: circle markers sized by capacity and coloured by technology, a popup with details, and a radius circle if given
  - highlight: polygon outline
  - auto-fit bounds to each new layer
  Clicking a municipality in the choropleth pre-fills the composer with "Tell me about <name>" (a small, nice-to-have touch).
- **ChartCard**: recharts `LineChart` for `chart_line`.
- **ResultTable**: a simple sortable table for `table` payloads; numbers formatted with thousands separators.
- Show a non-blocking toast or banner on errors, with a retry button for retryable errors.

### 7.5 Quality bar

- TypeScript `strict: true`, no `any` except at JSON parse boundaries (validate there with type guards).
- No secrets in the frontend. All LLM calls go through the backend.
- Must look clean and professional. Keep it simple; no design-system library is needed.
- `npm run build` must pass with zero TypeScript errors, and `npm run lint` must be clean.

---

## 8. MCP server (`backend/mcp_server/server.py`)

- Use `FastMCP` from the official `mcp` SDK, over the stdio transport.
- Expose **the same tools from the same registry**: `find_municipality`, `capacity_summary`, `rank_municipalities`, `units_near`, `capacity_timeseries`, `run_readonly_sql`. Call `django.setup()` at startup so the tools can use the DB.
- MCP tool results return `llm_content` as JSON text plus the one-line summary. Leave `display` payloads out, or trim them heavily; MCP clients don't need GeoJSON.
- Also expose one **MCP resource**, `wattwhere://schema`, with a markdown description of the tables and columns.
- Never write to stdout except MCP protocol messages. Send logs to stderr.
- Document in the README how to add it to **Claude Desktop** (`claude_desktop_config.json` snippet using `uv run --directory <abs path>/backend python -m mcp_server.server`) and how to test it with `npx @modelcontextprotocol/inspector`.
- **Design point for BUILD_LOG:** one tool layer, two front doors (the web agent and MCP). That's exactly "connect our applications to LLMs and to our own data, using APIs and MCP servers."

---

## 9. Evaluation (`backend/eval/`)

The user previously improved a RAG assistant from 70% to 95% accuracy with an evaluation set. Build the same discipline here.

- `questions.yaml`: **25 questions** across the categories lookup (5), ranking (5), spatial (5), time series (5), and edge cases (5: misspelled place names, out-of-scope questions, an ambiguous municipality name, a German-language question, a question that requires the SQL fallback).
- Each question has `expected`, computed **from the real database with direct SQL** by a helper (`eval/ground_truth.py`), never hand-typed. Also give each question an `expected_tools` list and, where relevant, `must_mention` keywords (e.g. the coordinates caveat).
- `run_eval.py` runs each question through the agent loop (not HTTP) and checks:
  - **numeric accuracy**: extract the key number(s) from the answer and compare them with ground truth within 1% (or exact for counts)
  - **tool correctness**: were the expected tools called?
  - **caveat compliance**: does the answer mention the required caveats?
  - **out-of-scope handling**: did it decline politely without inventing numbers?
- Outputs a markdown report, `docs/EVAL.md`, with per-category scores, failures with explanations, average latency and average tokens per question. Run it, then **improve the prompt and tool descriptions at least once** based on the failures. Record the before/after scores in `docs/EVAL.md` and in BUILD_LOG.
- The eval needs the real data and the API key. It is **not** part of `make test`.

---

## 10. Testing (`make test` must pass with no network and no API key)

Backend (pytest, against the `seed_sample` fixture in a test Postgres DB, i.e. the Docker DB with a test database):
- Each tool: happy path, empty result, bad input, unit conversions (kW → MW), per-capita maths.
- `sql_guard`: at least 15 cases. Allowed SELECTs pass. DML, DDL, multiple statements, comment tricks, disallowed tables, disallowed functions and `SELECT ... INTO` are all rejected. The timeout is enforced. The query runs as the read-only role (an attempted write fails at the DB level as well).
- Agent loop with a **fake Anthropic client** (a scripted sequence of streamed events, including a tool call): the right SSE events in the right order, the tool round limit, error handling, and disconnect handling.
- The SSE endpoint: content type, event framing.

Frontend (vitest):
- The SSE parser edge cases.
- The `useChat` reducer: event sequences produce the correct message state.

---

## 11. Configuration

`.env.example`:
```
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-5-5
DJANGO_SECRET_KEY=change-me
DJANGO_DEBUG=true
DATABASE_URL=postgres://wattwhere:wattwhere@localhost:5433/wattwhere
READONLY_DATABASE_URL=postgres://wattwhere_ro:wattwhere_ro@localhost:5433/wattwhere
REGION_LAND_PREFIX=08
REGION_NAME=Baden-Württemberg
OUTPUT_PATH=./data/open-mastr
```

Django settings read from env (use `django-environ` or plain `os.environ`). CORS isn't needed because Vite proxies `/api`. Set a request size limit on `/api/chat` and cap the history length (last 20 messages).

---

## 12. Makefile targets

```
make setup            # uv sync (backend) + npm install (frontend) + copy .env.example → .env if missing
make db-up            # docker compose up -d
make db-down
make migrate
make seed-sample      # small synthetic dataset (dev/tests)
make import-geo       # VG250-EW → municipalities
make import-mastr     # MaStR download (asks first) + import
make dev-backend      # uvicorn config.asgi:application --reload --port 8000
make dev-frontend     # vite on :5173
make test             # backend + frontend tests, offline
make lint
make eval             # requires real data + API key
make mcp-inspect      # run the MCP inspector against the server
```

---

## 13. Build phases and acceptance criteria

Work through these in order. After each phase: run the relevant checks, append to `docs/BUILD_LOG.md`, and (optionally) make a **local** git commit. **No push. No remote.**

### Phase 0: Preflight and scaffold
- Check for Docker, Node ≥ 20 and uv. Pin Python 3.12. Create the repo layout, `.gitignore` (`.env`, `data/`, `node_modules/`, `__pycache__/`, `.venv/`, `*.sqlite`, `dist/`), `.env.example`, Makefile skeleton and `docs/` stubs.
- ✅ `git status` shows no `.env` or `data/` files tracked. `make setup` works.

### Phase 1: Database and Django skeleton
- docker-compose with PostGIS (port 5433, named volume, healthcheck, init script creating `pg_trgm`, `postgis` and the `wattwhere_ro` role).
- Django project + `energy` and `agent` apps, models, migrations (including the `RunSQL` geometry columns and GIST indexes), and `/api/health`.
- ✅ `make db-up && make migrate` succeeds; `curl localhost:8000/api/health` returns JSON.

### Phase 2: Data ingestion
- `seed_sample` first. Then `import_municipalities` (VG250-EW). Then `import_mastr` (**ask the user before the big download**). Then inspect the schema → `docs/DATA.md` → importer.
- ✅ Baden-Württemberg has ~1,100 municipalities, all with geometry and population. Unit counts per technology are reported and plausible. The percentage of units with coordinates is recorded. `docs/DATA.md` is complete (sources, licences, snapshot date, column mapping, caveats).

### Phase 3: Tool layer
- All six tools + registry + `sql_guard` + tests.
- ✅ `make test` passes. A quick script prints sample outputs for Freiburg im Breisgau for each tool against the real data. Sanity-check these numbers and record them in BUILD_LOG.

### Phase 4: Agent and streaming endpoint
- Prompt, loop, events, view, fake-client tests.
- ✅ `curl -N -X POST localhost:8000/api/chat -H 'Content-Type: application/json' -d '{"messages":[{"role":"user","content":"How much solar capacity does Freiburg have?"}]}'` streams `text_delta`, `tool_call`, `tool_result`, `display` and `message_end` events.

### Phase 5: Frontend
- Everything in section 7.
- ✅ All 5 example questions in section 1 work end to end in the browser: streaming text, tool chips, a correct map layer and the chart where applicable. Stop works mid-stream. `npm run build` and `npm run lint` are clean.
- Take screenshots of 3 good answers (if you can, using whatever browser tooling you have; otherwise ask the user) and save them to `docs/screenshots/`.

### Phase 6: MCP server
- ✅ The MCP inspector lists all 6 tools and the schema resource. Calling `capacity_summary` for Freiburg returns sensible JSON. The README has the Claude Desktop config snippet.

### Phase 7: Evaluation
- ✅ `docs/EVAL.md` has a baseline and at least one improved run, with an explanation of what changed.

### Phase 8: Docs and polish
- **README.md**: a pitch (2–3 sentences linking the project to municipal energy planning), screenshots, an architecture diagram (Mermaid), quickstart (sample data in under 5 minutes; real data with the MaStR download), example questions, design decisions, eval results, limitations, data attributions. No mention of any specific employer in the README.
- **docs/ARCHITECTURE.md**: a request flow diagram (browser → Django SSE → agent loop → tools → PostGIS; MCP client → MCP server → the same tools), the event protocol, and the tool-layer design.
- Final check: from a clean state, `make setup && make db-up && make migrate && make seed-sample && make test` passes, and the app runs on the sample data.
- ✅ Give the user a final summary: what works, the known limitations, the eval scores, how to run it, and 5 talking points for an interview (design decisions and trade-offs).

---

## 14. Out of scope (don't build)

User accounts and auth, deployment, multiple regions at once, write access to data, vector search/RAG over documents, mobile layout, i18n of the UI chrome (the chat answers in the user's language; the UI labels can be English).

---

## 15. Final reminder

**Do not push to GitHub. Do not add a git remote. Do not use `gh`.** Local commits only, if any. Keep `.env` and `data/` out of git.
