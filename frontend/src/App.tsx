import { useEffect, useMemo, useState } from 'react'
import { ChartCard } from './components/ChartCard'
import { ChatPanel } from './components/ChatPanel'
import { MapView } from './components/MapView'
import { ResultTable } from './components/ResultTable'
import { useChat } from './hooks/useChat'
import { latestDisplays } from './lib/latestDisplays'

function useSnapshotDate(): string | null {
  const [date, setDate] = useState<string | null>(null)
  useEffect(() => {
    fetch('/api/health')
      .then((r) => r.json())
      .then((d: { data?: { snapshot?: Record<string, string> } }) =>
        setDate(d.data?.snapshot?.snapshot_date ?? null),
      )
      .catch(() => setDate(null))
  }, [])
  return date
}

export default function App() {
  const chat = useChat()
  const [draft, setDraft] = useState('') // composer text lives here so the map can pre-fill it
  const [resultsOpen, setResultsOpen] = useState(true)
  const snapshot = useSnapshotDate()

  // Recomputed only when the messages change.
  const { maps, chart, table } = useMemo(() => latestDisplays(chat.messages), [chat.messages])
  const hasResults = chart !== null || table !== null

  return (
    <div className="flex h-full flex-col">
      <main className="flex min-h-0 flex-1">
        <div className="h-full w-2/5 min-w-[340px] border-r border-slate-200">
          <ChatPanel
            messages={chat.messages}
            isStreaming={chat.isStreaming}
            error={chat.error}
            draft={draft}
            onDraftChange={setDraft}
            onSend={chat.send}
            onStop={chat.stop}
            onRetry={chat.retry}
            onDismissError={chat.dismissError}
          />
        </div>
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="min-h-0 flex-1">
            <MapView
              payloads={maps}
              onPickMunicipality={(name) => setDraft(`Tell me about ${name}`)}
            />
          </div>
          {hasResults && (
            <div className="border-t border-slate-200 bg-slate-50">
              <button
                type="button"
                onClick={() => setResultsOpen((o) => !o)}
                className="flex w-full items-center justify-between px-3 py-1.5 text-xs font-medium text-slate-600"
                aria-expanded={resultsOpen}
              >
                Results (chart &amp; table)
                <span>{resultsOpen ? '▾ hide' : '▸ show'}</span>
              </button>
              {resultsOpen && (
                <div className="grid max-h-[42vh] gap-3 overflow-auto p-3 xl:grid-cols-2">
                  {chart && <ChartCard chart={chart} />}
                  {table && <ResultTable table={table} />}
                </div>
              )}
            </div>
          )}
        </div>
      </main>
      <footer className="border-t border-slate-200 bg-white px-4 py-1.5 text-[11px] text-slate-500">
        Datenquelle: Marktstammdatenregister (Bundesnetzagentur), dl-de/by-2-0 · © BKG 2025,
        dl-de/by-2-0 · Map © OpenStreetMap contributors
        {snapshot && <> · Data snapshot: {snapshot}</>}
      </footer>
    </div>
  )
}
