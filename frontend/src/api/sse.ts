// Reading a Server-Sent Events stream from a POST request.
//
// The browser's built-in `EventSource` can only make GET requests, but we must POST the chat
// history. So we use `fetch`, read the response body as a stream of bytes, and parse the
// SSE text format ourselves:
//
//     event: text_delta\n
//     data: {"text": "Hi"}\n
//     \n                      <- a blank line ends one message ("frame")
//     : ping\n\n              <- lines starting with ':' are comments (heartbeats)

import type { ChatEvent, DisplayPayload, HistoryMessage } from './types'

export interface SSEFrame {
  event: string
  data: string
}

/**
 * Incremental SSE parser. Network chunks can cut a frame anywhere (even mid-line or between the
 * two newlines), and one chunk can hold several frames. So we keep leftover text in `buffer`
 * and only emit frames once we have seen their terminating blank line.
 */
export class SSEParser {
  private buffer = ''

  push(chunk: string): SSEFrame[] {
    this.buffer += chunk
    // Normalise Windows/old-Mac line endings so we only deal with '\n'.
    this.buffer = this.buffer.replace(/\r\n/g, '\n').replace(/\r/g, '\n')
    const frames: SSEFrame[] = []
    let boundary = this.buffer.indexOf('\n\n')
    while (boundary !== -1) {
      const raw = this.buffer.slice(0, boundary)
      this.buffer = this.buffer.slice(boundary + 2)
      const frame = parseFrame(raw)
      if (frame) frames.push(frame)
      boundary = this.buffer.indexOf('\n\n')
    }
    return frames
  }
}

function parseFrame(raw: string): SSEFrame | null {
  let event = 'message' // SSE default event name
  const data: string[] = []
  for (const line of raw.split('\n')) {
    if (line === '' || line.startsWith(':')) continue // blank or comment (heartbeat)
    const colon = line.indexOf(':')
    const field = colon === -1 ? line : line.slice(0, colon)
    let value = colon === -1 ? '' : line.slice(colon + 1)
    if (value.startsWith(' ')) value = value.slice(1) // one optional space after the colon
    if (field === 'event') event = value
    else if (field === 'data') data.push(value) // several data: lines are joined with \n
  }
  if (data.length === 0) return null // comment-only frame
  return { event, data: data.join('\n') }
}

// ---- Validation at the JSON boundary (the only place we touch untyped data) ----

function isRecord(x: unknown): x is Record<string, unknown> {
  return typeof x === 'object' && x !== null && !Array.isArray(x)
}

function isFeatureCollection(x: unknown): boolean {
  return isRecord(x) && x.type === 'FeatureCollection' && Array.isArray(x.features)
}

export function isDisplayPayload(x: unknown): x is DisplayPayload {
  if (!isRecord(x) || typeof x.title !== 'string') return false
  switch (x.kind) {
    case 'map_choropleth':
      return typeof x.unit === 'string' && isFeatureCollection(x.geojson)
    case 'map_points':
    case 'map_highlight':
      return isFeatureCollection(x.geojson)
    case 'chart_line':
      return Array.isArray(x.x) && Array.isArray(x.series) && typeof x.y_unit === 'string'
    case 'table':
      return Array.isArray(x.columns) && Array.isArray(x.rows)
    default:
      return false
  }
}

/** Turn a parsed frame into a typed ChatEvent, or null if it is malformed/unknown. */
export function toChatEvent(frame: SSEFrame): ChatEvent | null {
  let d: unknown
  try {
    d = JSON.parse(frame.data)
  } catch {
    return null
  }
  if (!isRecord(d)) return null
  switch (frame.event) {
    case 'message_start':
      return typeof d.id === 'string' ? { type: 'message_start', id: d.id } : null
    case 'text_delta':
      return typeof d.text === 'string' ? { type: 'text_delta', text: d.text } : null
    case 'tool_call':
      return typeof d.id === 'string' && typeof d.name === 'string' && isRecord(d.input)
        ? { type: 'tool_call', id: d.id, name: d.name, input: d.input }
        : null
    case 'tool_result':
      return typeof d.id === 'string' &&
        typeof d.name === 'string' &&
        typeof d.summary === 'string' &&
        typeof d.ok === 'boolean'
        ? {
            type: 'tool_result',
            id: d.id,
            name: d.name,
            summary: d.summary,
            ok: d.ok,
            duration_ms: typeof d.duration_ms === 'number' ? d.duration_ms : 0,
          }
        : null
    case 'display':
      return typeof d.tool_call_id === 'string' && isDisplayPayload(d.payload)
        ? { type: 'display', tool_call_id: d.tool_call_id, payload: d.payload }
        : null
    case 'error':
      return typeof d.message === 'string'
        ? { type: 'error', message: d.message, retryable: d.retryable === true }
        : null
    case 'message_end':
      return isRecord(d.usage) && typeof d.stop_reason === 'string'
        ? {
            type: 'message_end',
            usage: {
              input_tokens: Number(d.usage.input_tokens ?? 0),
              output_tokens: Number(d.usage.output_tokens ?? 0),
              cache_read_input_tokens: Number(d.usage.cache_read_input_tokens ?? 0),
            },
            stop_reason: d.stop_reason,
          }
        : null
    default:
      return null
  }
}

/**
 * POST the conversation and yield events as they arrive.
 * An `async function*` is an "async generator": consumers write `for await (const e of streamChat(...))`.
 * Aborting `signal` cancels the fetch, which makes the server stop the LLM call too.
 */
export async function* streamChat(
  messages: HistoryMessage[],
  signal: AbortSignal,
): AsyncGenerator<ChatEvent> {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages }),
    signal,
  })
  if (!response.ok || !response.body) {
    throw new Error(`The server answered with an error (HTTP ${response.status}).`)
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder() // turns bytes into text; remembers half-received characters
  const parser = new SSEParser()
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      for (const frame of parser.push(decoder.decode(value, { stream: true }))) {
        const event = toChatEvent(frame)
        if (event) yield event
      }
    }
  } finally {
    reader.releaseLock()
  }
}
