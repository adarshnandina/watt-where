import { describe, expect, it } from 'vitest'
import { SSEParser, isDisplayPayload, toChatEvent } from './sse'

const frame = (event: string, data: unknown) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`

describe('SSEParser', () => {
  it('parses a single complete frame', () => {
    const p = new SSEParser()
    expect(p.push(frame('text_delta', { text: 'Hi' }))).toEqual([
      { event: 'text_delta', data: '{"text":"Hi"}' },
    ])
  })

  it('parses several frames delivered in one chunk', () => {
    const p = new SSEParser()
    const frames = p.push(frame('text_delta', { text: 'a' }) + frame('text_delta', { text: 'b' }))
    expect(frames.map((f) => f.data)).toEqual(['{"text":"a"}', '{"text":"b"}'])
  })

  it('reassembles a frame split across chunks at any position', () => {
    const whole = frame('tool_call', { id: 't1', name: 'x', input: {} })
    for (let cut = 1; cut < whole.length; cut++) {
      const p = new SSEParser()
      const out = [...p.push(whole.slice(0, cut)), ...p.push(whole.slice(cut))]
      expect(out).toHaveLength(1)
      expect(out[0].event).toBe('tool_call')
    }
  })

  it('handles the blank-line terminator arriving in a separate chunk', () => {
    const p = new SSEParser()
    expect(p.push('event: text_delta\ndata: {"text":"x"}\n')).toEqual([])
    expect(p.push('\n')).toHaveLength(1)
  })

  it('ignores comment/heartbeat lines', () => {
    const p = new SSEParser()
    expect(p.push(': ping\n\n')).toEqual([])
    const out = p.push(': ping\n\n' + frame('text_delta', { text: 'x' }))
    expect(out).toHaveLength(1)
  })

  it('joins multiple data lines with a newline and handles CRLF', () => {
    const p = new SSEParser()
    expect(p.push('event: x\r\ndata: a\r\ndata: b\r\n\r\n')).toEqual([{ event: 'x', data: 'a\nb' }])
  })

  it('defaults the event name to "message" and keeps unicode intact', () => {
    const p = new SSEParser()
    expect(p.push('data: Grüße €\n\n')).toEqual([{ event: 'message', data: 'Grüße €' }])
  })
})

describe('toChatEvent (validation at the JSON boundary)', () => {
  it('builds typed events', () => {
    expect(toChatEvent({ event: 'text_delta', data: '{"text":"Hi"}' })).toEqual({
      type: 'text_delta',
      text: 'Hi',
    })
    expect(
      toChatEvent({
        event: 'tool_result',
        data: '{"id":"t","name":"n","summary":"s","ok":false,"duration_ms":5}',
      }),
    ).toMatchObject({ type: 'tool_result', ok: false, duration_ms: 5 })
  })

  it('rejects malformed JSON, wrong shapes and unknown events', () => {
    expect(toChatEvent({ event: 'text_delta', data: 'not json' })).toBeNull()
    expect(toChatEvent({ event: 'text_delta', data: '{"text":5}' })).toBeNull()
    expect(toChatEvent({ event: 'mystery', data: '{}' })).toBeNull()
    expect(
      toChatEvent({ event: 'display', data: '{"tool_call_id":"t","payload":{"kind":"x"}}' }),
    ).toBeNull()
  })

  it('validates display payload kinds', () => {
    const fc = { type: 'FeatureCollection', features: [] }
    expect(isDisplayPayload({ kind: 'map_highlight', title: 't', geojson: fc })).toBe(true)
    expect(isDisplayPayload({ kind: 'map_highlight', title: 't', geojson: {} })).toBe(false)
    expect(isDisplayPayload({ kind: 'table', title: 't', columns: [], rows: [] })).toBe(true)
    expect(
      isDisplayPayload({ kind: 'chart_line', title: 't', x: [], series: [], y_unit: 'MW' }),
    ).toBe(true)
    expect(isDisplayPayload(null)).toBe(false)
  })
})
