# Build Log

Plain-language notes on what was built and why, one entry per phase.

## Phase 0: Preflight and scaffold
**Built:** git repo (local only, no remote), `.gitignore` (covers `.env`, `data/`, `node_modules/`, venvs, sqlite), `.env.example`, Makefile, `docs/` stubs, a `uv` backend project pinned to Python 3.12 with all backend dependencies, and a Vite + React + TypeScript frontend with leaflet, react-leaflet, recharts, react-markdown, remark-gfm, Tailwind v4, vitest and prettier.

**Decisions / deviations:**
- Python is pinned to 3.12 because some geo/data wheels don't support the system's 3.14 yet.
- `.claude/` is also git-ignored (local tooling config, not part of the project).
- Package versions are whatever resolved today (e.g. React 19, Vite 8, TypeScript 7). The spec said "React 18+", so 19 is fine.
- Docker CLI is installed but the daemon was not running at preflight time. Needed from Phase 1.
