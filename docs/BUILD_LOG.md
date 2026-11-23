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
