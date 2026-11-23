// Event and payload types for the chat stream.
// These mirror backend/agent/events.py - if you change one side, change the other.

import type { FeatureCollection } from 'geojson'

export type Role = 'user' | 'assistant'
export interface HistoryMessage {
  role: Role
  content: string
}

// ---- What the backend can ask the UI to draw ("display payloads") ----
export type DisplayPayload =
  | { kind: 'map_choropleth'; title: string; unit: string; geojson: FeatureCollection }
  | {
      kind: 'map_points'
      title: string
      geojson: FeatureCollection
      circle?: { lat: number; lon: number; radius_km: number }
    }
  | { kind: 'map_highlight'; title: string; geojson: FeatureCollection }
  | {
      kind: 'chart_line'
      title: string
      x: (string | number)[]
      series: { name: string; values: number[] }[]
      y_unit: string
    }
  | {
      kind: 'table'
      title: string
      columns: string[]
      rows: (string | number | null)[][]
    }

export type TableData = Extract<DisplayPayload, { kind: 'table' }>
export type ChartData = Extract<DisplayPayload, { kind: 'chart_line' }>
export type MapPayload = Extract<
  DisplayPayload,
  { kind: 'map_choropleth' | 'map_points' | 'map_highlight' }
>

export interface Usage {
  input_tokens: number
  output_tokens: number
  cache_read_input_tokens?: number
}

// ---- The server-sent events, as a discriminated union on `type` ----
export type ChatEvent =
  | { type: 'message_start'; id: string }
  | { type: 'text_delta'; text: string }
  | { type: 'tool_call'; id: string; name: string; input: Record<string, unknown> }
  | {
      type: 'tool_result'
      id: string
      name: string
      summary: string
      ok: boolean
      duration_ms: number
    }
  | { type: 'display'; tool_call_id: string; payload: DisplayPayload }
  | { type: 'error'; message: string; retryable: boolean }
  | { type: 'message_end'; usage: Usage; stop_reason: string }
