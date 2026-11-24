import { describe, expect, it } from 'vitest'
import type { ChatEvent } from '../api/types'
import { chatReducer, initialState, toHistory, type ChatAction, type ChatState } from './useChat'

const run = (actions: ChatAction[], from: ChatState = initialState) =>
  actions.reduce(chatReducer, from)
const ev = (event: ChatEvent): ChatAction => ({ type: 'event', event })
const send = (text = 'Q'): ChatAction => ({ type: 'send', userId: 'u', assistantId: 'a', text })
const table = { kind: 'table' as const, title: 'T', columns: ['a'], rows: [[1]] }

describe('chatReducer', () => {
  it('send adds the user message and an empty streaming assistant message', () => {
    const s = run([send('Hello')])
    expect(s.isStreaming).toBe(true)
    expect(s.messages.map((m) => [m.role, m.text, m.streaming])).toEqual([
      ['user', 'Hello', false],
      ['assistant', '', true],
    ])
  })

  it('a full tool-using answer produces the right message state', () => {
    const s = run([
      send(),
      ev({ type: 'message_start', id: 'x' }),
      ev({ type: 'text_delta', text: 'Let me ' }),
      ev({ type: 'tool_call', id: 't1', name: 'capacity_summary', input: { area: 'region' } }),
      ev({
        type: 'tool_result',
        id: 't1',
        name: 'capacity_summary',
        summary: '3 units',
        ok: true,
        duration_ms: 40,
      }),
      ev({ type: 'display', tool_call_id: 't1', payload: table }),
      ev({ type: 'text_delta', text: 'check.' }),
      ev({
        type: 'message_end',
        usage: { input_tokens: 1, output_tokens: 1 },
        stop_reason: 'end_turn',
      }),
    ])
    const a = s.messages[1]
    expect(a.text).toBe('Let me check.')
    expect(a.toolCalls).toEqual([
      {
        id: 't1',
        name: 'capacity_summary',
        input: { area: 'region' },
        status: 'ok',
        summary: '3 units',
        durationMs: 40,
      },
    ])
    expect(a.displays).toEqual([{ toolCallId: 't1', payload: table }])
    expect(a.streaming).toBe(false)
    expect(s.isStreaming).toBe(false)
  })

  it('tool chip is pending until its result arrives, and error results are marked', () => {
    let s = run([send(), ev({ type: 'tool_call', id: 't', name: 'n', input: {} })])
    expect(s.messages[1].toolCalls[0].status).toBe('pending')
    s = run(
      [
        ev({
          type: 'tool_result',
          id: 't',
          name: 'n',
          summary: 'Error: x',
          ok: false,
          duration_ms: 1,
        }),
      ],
      s,
    )
    expect(s.messages[1].toolCalls[0].status).toBe('error')
  })

  it('does not mutate the previous state', () => {
    const before = run([send()])
    const snapshot = JSON.stringify(before)
    run([ev({ type: 'text_delta', text: 'x' })], before)
    expect(JSON.stringify(before)).toBe(snapshot)
  })

  it('error events set the banner without discarding the partial answer', () => {
    const s = run([
      send(),
      ev({ type: 'text_delta', text: 'part' }),
      ev({ type: 'error', message: 'busy', retryable: true }),
    ])
    expect(s.error).toEqual({ message: 'busy', retryable: true })
    expect(s.messages[1].text).toBe('part')
  })

  it('finish (Stop) ends streaming and un-sticks pending tool chips', () => {
    const s = run([
      send(),
      ev({ type: 'tool_call', id: 't', name: 'n', input: {} }),
      { type: 'finish' },
    ])
    expect(s.isStreaming).toBe(false)
    expect(s.messages[1].streaming).toBe(false)
    expect(s.messages[1].toolCalls[0].status).toBe('error')
  })

  it('fail sets a retryable error; dismiss clears it', () => {
    let s = run([send(), { type: 'fail', message: 'offline' }])
    expect(s.error).toEqual({ message: 'offline', retryable: true })
    s = run([{ type: 'dismiss_error' }], s)
    expect(s.error).toBeNull()
  })

  it('drop_last_turn removes the failed user+assistant pair', () => {
    const s = run([send('one'), { type: 'finish' }, { type: 'drop_last_turn' }])
    expect(s.messages).toEqual([])
  })

  it('reset returns to the empty initial state, even mid-stream', () => {
    const s = run([send(), ev({ type: 'text_delta', text: 'partial' }), { type: 'reset' }])
    expect(s).toEqual(initialState)
  })

  it('a late finish after reset does not resurrect anything', () => {
    const s = run([send(), { type: 'reset' }, { type: 'finish' }])
    expect(s.messages).toEqual([])
    expect(s.isStreaming).toBe(false)
  })

  it('toHistory sends only non-empty visible text', () => {
    const s = run([
      send('Q1'),
      ev({ type: 'text_delta', text: 'A1' }),
      { type: 'finish' },
      { type: 'send', userId: 'u2', assistantId: 'a2', text: 'Q2' },
    ])
    expect(toHistory(s.messages)).toEqual([
      { role: 'user', content: 'Q1' },
      { role: 'assistant', content: 'A1' },
      { role: 'user', content: 'Q2' },
    ])
  })
})
