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
