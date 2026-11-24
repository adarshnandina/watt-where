# WattWhere frontend

React 19 + TypeScript (strict) + Vite + Tailwind CSS v4. Talks only to the backend's `/api` (Vite proxies it to `http://localhost:8000`), so there are no secrets or backend URLs in this code.

## Run

```bash
npm install
npm run dev        # http://localhost:5173 (backend must be running on :8000)
npm test           # vitest (offline)
npm run lint       # oxlint + prettier --check
npm run build      # type-check + production build into dist/
```

From the repository root, `make dev-frontend`, `make test` and `make lint` do the same.

## Structure

```
src/
  api/        sse.ts (POST-based SSE parser + type guards at the JSON boundary), types.ts (mirrors backend/agent/events.py)
  hooks/      useChat.ts: reducer + hook that holds all chat state and runs the stream
  components/ ChatPanel, MessageList, Message, ToolCallChip, Composer, ExampleQuestions,
              MapView (Leaflet), ChartCard (Recharts), ResultTable, Splitter, icons
  lib/        layout.ts (panel-size maths + persistence), theme.ts / ThemeProvider.tsx, colors.ts,
              latestDisplays.ts (what the map/chart/table show), quantiles.ts (choropleth classes)
  App.tsx     layout: resizable chat | map | results
```

## How a message flows

`Composer` → `useChat.send` → `streamChat` (`fetch` + stream reader) → parsed events → `chatReducer` → components re-render.
Tool results arrive as `display` events with typed payloads (`map_choropleth`, `map_points`, `map_highlight`, `chart_line`, `table`); `latestDisplays()` decides which ones the right-hand side shows.

## Conventions

- **State changes go through the reducer** (pure, unit-tested); components only render.
- **No `any`.** Untyped JSON is validated once, in `api/sse.ts`.
- **Colours are CSS variables** defined in `index.css`; dark mode overrides the same names under `html.dark`. Colours needed in JavaScript (map, chart) come from `useTheme()`.
- **Panel sizes** are stored as fractions in `localStorage` (`ww.*` keys); the theme in `ww.theme`.
- Tests use `react-dom/server` to render components to HTML (no DOM library needed).
