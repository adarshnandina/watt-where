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

## Phase 4: Agent and streaming endpoint
**Built:** `agent/events.py` (event protocol + SSE encoding + heartbeat), `agent/prompts.py`, `agent/loop.py`, `agent/views.py` (`POST /api/chat`, `GET /api/examples`, `GET /api/municipalities/search`). 27 new tests with a scripted fake Anthropic client (110 total, all offline).

**Design decisions:**
- **Agent loop = async generator of events.** `run_agent()` yields `(type, data)` tuples and knows nothing about HTTP. The view wraps it in `with_heartbeat()` which encodes SSE frames. That separation made it testable without a network.
- **The loop is the whole "agent":** stream a model turn → if it asked for tools, run them (concurrently with `asyncio.gather`, in worker threads because the DB layer is sync) → append `tool_result` blocks → stream the next turn. Capped at 8 tool rounds; on the cap it ends with a polite message and `stop_reason: max_tool_rounds`.
- **Context discipline:** the model receives `llm_content` JSON only. The test `test_tool_round_event_order_and_what_the_model_sees` asserts display payloads never reach the second API call.
- **Prompt caching:** `cache_control` on the system block and on the last tool definition (the API caches everything up to that marker). Cache-read tokens are summed into `usage` and logged.
- **Heartbeat via producer task + queue:** a slow tool can't block the `: ping` comment. When the client disconnects, the wrapper's `finally` cancels the agent task, which closes the LLM stream and prevents further rounds. Tested.
- **Retry policy:** one retry with backoff for rate limits / overload / connection errors, but only if no text had been streamed yet in that round (otherwise the user would see duplicated text). Then an `error` event with a generic message; auth errors are non-retryable and never leak details or keys.
- **Stateless backend:** the client sends visible text history only (last 20 messages, each capped at 4,000 chars, body max 64 KB). Earlier tool calls aren't replayed to the model. **Deliberate simplification:** follow-ups work from the text of previous answers, which is cheaper and simpler; the cost is that the model can't re-read old tool outputs.
- Errors also end with `message_end` (`stop_reason: "error"`), so the client always gets a terminator.
- Structured JSON log line per request (question, tools+durations, tokens, stop reason) to stdout; the key is never logged.

**Deviation / gotchas:**
- The installed `anthropic` SDK (2.12) uses `httpx2`, so test fakes build errors with `httpx2`. I verified `messages.stream(...)`, `text_stream` and `get_final_message()` exist in the installed version rather than trusting memory.
- **Not yet verified live:** `.env` still holds the placeholder `ANTHROPIC_API_KEY`, so the curl acceptance check against the real model could not run. Verified instead: real uvicorn serves proper SSE headers/framing, the no-key path returns a clean `error` event, bad bodies return 400, examples and municipality search work. Live check is pending the user's key.

## Phase 5: Frontend
**Built:** Vite + React + TypeScript (`strict: true`) app. `api/sse.ts` (POST-based SSE client + parser + type guards), `api/types.ts` (mirrors `agent/events.py`), `hooks/useChat.ts` (reducer), components (`ChatPanel`, `MessageList`, `Message`, `ToolCallChip`, `Composer`, `ExampleQuestions`, `MapView`, `ChartCard`, `ResultTable`), footer with attributions + data snapshot date. 23 vitest tests; `npm run build` has zero TypeScript errors; `npm run lint` is clean.

**Design decisions:**
- **`fetch` + stream reader instead of `EventSource`:** `EventSource` can't POST. The parser keeps a buffer, so frames split across network chunks (tested at *every* cut position), several frames per chunk, CRLF, comment/heartbeat lines and multi-line `data:` all work.
- **Reducer for chat state:** one streamed event often changes several things; a pure reducer is easy to reason about and to unit-test. It also makes "Stop" safe: `finish` un-sticks tool chips that never got a result.
- **Validation only at the JSON boundary:** `toChatEvent` turns untyped JSON into the typed `ChatEvent` union (or `null`). No `any` anywhere else.
- **Map/chart/table are derived state:** `latestDisplays(messages)` picks what to show. Nothing is stored twice.
- **Quantile classes** for the choropleth (duplicate breaks collapse, since many municipalities have 0 MW of wind), legend with units, hover tooltip, click pre-fills "Tell me about X".
- The retry button removes the whole failed turn and re-sends it, so history never contains a duplicate question.

**Deviations:**
- The Vite template ships **oxlint**, not ESLint. I kept it (plus `prettier --check`) rather than add an ESLint toolchain; it covers the React hooks rules and runs in milliseconds. Easy to swap if ESLint is required.
- React 19 / Vite 8 / TypeScript 7 (see Phase 0).
- Bundle is ~980 kB (Leaflet + Recharts + markdown). Fine for a demo; code-splitting would be the next step.

**NOT yet verified (be honest in interviews):**
- The browser end-to-end run of the 5 example questions, the Stop button mid-stream, and the 3 screenshots in `docs/screenshots/`. These need a real `ANTHROPIC_API_KEY` in `.env` (still the placeholder) and a browser. What *was* verified: all real tool payloads from the real database pass the frontend type guards (so no display would be silently dropped), the SSE protocol works over real uvicorn, and the unit tests above.

## Phase 6: MCP server
**Built:** `backend/mcp_server/server.py` (stdio), 5 in-process tests, README section with the Claude Desktop config. Verified three ways: a real MCP client over stdio (lists the 6 tools + `wattwhere://schema`, `capacity_summary` for Freiburg solar returns 103.83 MW, bad input is flagged `isError`), the official **MCP Inspector CLI** (`tools/list` shows all six), and pytest.

**Design point (interview material): one tool layer, two front doors.** The server contains no tool logic. It loops over `energy.tools.REGISTRY` and registers each tool with the registry's own description and JSON schema. The web agent reads the same registry. A fix or new tool is made once and appears in both places.

**Details that bit me:**
- `mcp` 2.x renamed `FastMCP` to `MCPServer` (`mcp.server.mcpserver`). Same official SDK, so I used it and checked the actual API rather than writing 1.x code. (Deviation from the spec's name only.)
- The SDK passes unset optional parameters as `None`, but the registry's strict JSON schema means "omitted", so the handler drops `None`s first.
- Reusing the function's signature leaked its `-> ToolResult` return annotation, which the SDK tried to treat as structured output. Fixed with an explicit signature returning `str`.
- Sync tools run in worker threads; the handler closes their DB connections after each call.
- `display` payloads (GeoJSON) are intentionally omitted from MCP results; clients get `llm_content` JSON plus the one-line summary. Errors raise `ToolError` so clients see `isError`.
- stdout is the protocol channel; logging is configured to stderr before anything else is imported.
- I override the SDK's inferred schema using its internal `_tool_manager` attribute so clients see enums/ranges. It's the one place that relies on a private attribute; a test (`test_lists_exactly_the_registry_tools_with_registry_schemas`) will fail loudly if an SDK upgrade breaks it.

## Phase 7: Evaluation (harness built; NOT yet run)
**Built:** `backend/eval/questions.yaml` (25 questions: 5 lookup, 5 ranking, 5 spatial, 5 time series, 5 edge cases incl. a typo, an out-of-scope question, an ambiguous name (Altdorf exists in two districts), German, and one that needs the SQL fallback), `ground_truth.py`, `run_eval.py`, 5 offline tests of the scorer.

**Design:**
- Expected values come from `ground_truth.py`: hand-written SQL that deliberately does not import the tools, so it is an independent check. I printed all 25 truths against the real DB; they agree with the tool outputs from Phase 3 (e.g. Freiburg solar 103.83 MW, wind within 25 km 23 units / 57.63 MW).
- Checks: numeric (counts exact, other figures ±1%, tolerant of English/German number formats and kW↔MW phrasing), expected tools called, caveat phrases, out-of-scope (declines, calls no data tools, quotes no figures), language, and "no error events".
- `--truth-only` prints ground truth without an API key. `--label` stores a run in `eval/results/`; `docs/EVAL.md` is regenerated from all stored runs, with `eval/CHANGES.md` explaining what changed between them. Each run records a hash of system prompt + tool definitions so it is clear which runs used which prompt.
- Questions are phrased so the truth is unambiguous (e.g. the per-capita ranking states "at least 1,000 inhabitants").

**Status:** the LLM run itself needs `ANTHROPIC_API_KEY` (placeholder in `.env`). No baseline or improved score exists yet; `docs/EVAL.md` stays a stub until then. I won't invent scores.

### Phase 7 update: evaluation run (live)
Baseline 22/25 -> 24/25 after fixing two eval mistakes (same prompt) -> **25/25** (twice) after one prompt/tool-description change. Full table, reasoning and failure analysis: `docs/EVAL.md`, `backend/eval/CHANGES.md`. Model: `claude-haiku-5-5`. Average latency ~4 s per question.

**Phase 4 live check done:** `curl -N` against `/api/chat` streams `message_start, tool_call, tool_result, display, text_delta, message_end`; prompt caching works (6k cache-read tokens on the second request).

**Bug found only by the live run:** `thinking` content blocks crashed the loop (it only knew `text` and `tool_use`). Now passed back unchanged, as the API requires; regression test added. A reminder of why fake-client tests alone are not enough.
**Ops note:** the Docker container stopped when Docker restarted; `make db-up` brings it back with data intact (named volume).

## Phase 5 update: end-to-end through the real stack (no browser available)
No browser tooling was available in this environment, so I could not take screenshots or watch the UI render. Instead I sent all 5 spec example questions through the Vite proxy (`:5173/api/chat`) to Django and Claude, and checked events, tools and display payloads: all five completed with `end_turn`, no errors; payloads were a 1,103-feature choropleth, 23 map points, line charts, tables, and highlight polygons; figures matched the ground truth (e.g. 103.8 MW, 23 turbines / 57.6 MW).

**Found by doing this:** question 5 revealed that the model guessed a district key (`08316` is Emmendingen, not Breisgau-Hochschwarzwald) and its self-correction leaked into the answer. Root cause was a tool gap: `find_municipality` could not look up districts. Fixed: it now also returns matching districts; prompt/tool text say "never guess a key"; test added. Eval re-run (`final`): 25/25. The eval had not caught this, a reminder that 25 questions are a floor, not proof.

**Still unverified by a human eye:** visual layout, map colours/legend, the Stop button behaviour in a real browser, and the screenshots (`docs/screenshots/` is empty).

## Phase 8: Docs and polish
README (pitch, Mermaid diagram, quickstart, design decisions, eval results, limitations, attributions; no employer mentioned), `docs/ARCHITECTURE.md`. The spec's "from a clean state" check was **not** run destructively because `make seed-sample` would truncate the real data in the dev DB; instead each `pytest` run builds a fresh test database from migrations and seeds it, which exercises the same path.

## UI update: New chat button and resizable panels
- **New chat** (header button, shown once a conversation exists): aborts any running request first, then a `reset` action returns the reducer to its initial state, and the composer draft is cleared. Aborting first matters: otherwise a late stream event could land in the new conversation. Reducer tests cover reset mid-stream and a late `finish` after reset.
- **Resizable panels:** a reusable `Splitter` (pointer capture, so dragging keeps working when the cursor crosses the map; arrow keys work too, `role="separator"`) between chat | map, map | results, and chart | table. Sizes are stored as fractions of their container (clamped, persisted in `localStorage` via `usePersistentFraction`), so they survive reloads and window resizes.
- Leaflet only measures its container once, so a `ResizeObserver` inside the map calls `invalidateSize()` whenever the panel changes size. Without that the map would show grey tiles after dragging.
- Chart and table now fill their panel instead of using fixed heights.
- Verified: typecheck, lint, 27 unit tests (layout maths + reducer), production build. **Not verified visually** (no browser available here): please drag the three dividers and click New chat once.
