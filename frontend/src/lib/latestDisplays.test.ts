import { expect, it } from 'vitest'
import type { ChatMessage } from '../hooks/useChat'
import { latestDisplays } from './latestDisplays'

const fc = { type: 'FeatureCollection' as const, features: [] }
const msg = (displays: ChatMessage['displays']): ChatMessage => ({
  id: 'x',
  role: 'assistant',
  text: '',
  toolCalls: [],
  displays,
  streaming: false,
})

it('picks the newest map layers, chart and table', () => {
  const old = msg([
    { toolCallId: 'a', payload: { kind: 'map_highlight', title: 'old', geojson: fc } },
  ])
  const newer = msg([
    { toolCallId: 'b', payload: { kind: 'map_points', title: 'new', geojson: fc } },
    { toolCallId: 'b', payload: { kind: 'table', title: 'tbl', columns: [], rows: [] } },
  ])
  const r = latestDisplays([old, newer])
  expect(r.maps.map((m) => m.title)).toEqual(['new'])
  expect(r.table?.title).toBe('tbl')
  expect(r.chart).toBeNull()
})

it('is empty for an empty conversation', () => {
  expect(latestDisplays([])).toEqual({ maps: [], chart: null, table: null })
})
