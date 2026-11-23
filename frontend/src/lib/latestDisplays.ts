import type { ChatMessage } from '../hooks/useChat'
import type { ChartData, MapPayload, TableData } from '../api/types'

export interface LatestDisplays {
  maps: MapPayload[]
  chart: ChartData | null
  table: TableData | null
}

/**
 * Which things should the right-hand side show right now?
 *  - map: all map layers from the most recent assistant message that produced any
 *  - chart / table: the most recent one anywhere in the conversation
 */
export function latestDisplays(messages: ChatMessage[]): LatestDisplays {
  let maps: MapPayload[] = []
  let chart: ChartData | null = null
  let table: TableData | null = null
  for (let i = messages.length - 1; i >= 0; i--) {
    const items = messages[i].displays
    if (maps.length === 0) {
      maps = items.flatMap((d) =>
        d.payload.kind.startsWith('map_') ? [d.payload as MapPayload] : [],
      )
    }
    for (let j = items.length - 1; j >= 0; j--) {
      const p = items[j].payload
      if (!chart && p.kind === 'chart_line') chart = p
      if (!table && p.kind === 'table') table = p
    }
  }
  return { maps, chart, table }
}
