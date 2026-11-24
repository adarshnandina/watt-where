import { useEffect, useMemo, useRef, useState } from 'react'
import { ChartCard } from './components/ChartCard'
import { ChatPanel } from './components/ChatPanel'
import { ChevronIcon } from './components/icons'
import { MapView } from './components/MapView'
import { ResultTable } from './components/ResultTable'
import { Splitter } from './components/Splitter'
import { useChat } from './hooks/useChat'
import { latestDisplays } from './lib/latestDisplays'
import { usePersistentFraction } from './lib/layout'

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

  // Panel sizes, as fractions of their container (kept in localStorage):
  //  chatFrac:  chat width / total width       mapFrac:   map height / right-column height
  //  chartFrac: chart width / results width
  const [chatFrac, setChatFrac] = usePersistentFraction('ww.chatFrac', 0.4, 0.2, 0.7)
  const [mapFrac, setMapFrac] = usePersistentFraction('ww.mapFrac', 0.6, 0.2, 0.85)
  const [chartFrac, setChartFrac] = usePersistentFraction('ww.chartFrac', 0.5, 0.2, 0.8)
  // Refs give the splitters the container they measure the pointer against.
  const mainRef = useRef<HTMLElement>(null)
  const rightRef = useRef<HTMLDivElement>(null)
  const resultsRef = useRef<HTMLDivElement>(null)

  // Recomputed only when the messages change.
  const { maps, chart, table } = useMemo(() => latestDisplays(chat.messages), [chat.messages])
  const hasResults = chart !== null || table !== null
  const showBody = hasResults && resultsOpen

  const newChat = () => {
    chat.clear()
    setDraft('')
  }

  return (
    <div className="flex h-full flex-col bg-page">
      <main ref={mainRef} className="flex min-h-0 flex-1">
        <div className="h-full min-w-[300px]" style={{ width: `${chatFrac * 100}%` }}>
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
            onNewChat={newChat}
          />
        </div>
        <Splitter
          orientation="vertical"
          containerRef={mainRef}
          onChange={setChatFrac}
          current={chatFrac}
          label="Resize chat and map"
        />

        {/* Right side: floating rounded cards on the page background */}
        <div ref={rightRef} className="flex min-w-0 flex-1 flex-col py-3 pr-3">
          <div
            className="min-h-[120px] overflow-hidden rounded-2xl border border-line bg-card shadow-sm"
            style={showBody ? { height: `${mapFrac * 100}%` } : { flex: '1 1 0%' }}
          >
            <MapView
              payloads={maps}
              onPickMunicipality={(name) => setDraft(`Tell me about ${name}`)}
            />
          </div>
          {hasResults && (
            <>
              {showBody ? (
                <Splitter
                  orientation="horizontal"
                  containerRef={rightRef}
                  onChange={setMapFrac}
                  current={mapFrac}
                  label="Resize map and results"
                />
              ) : (
                <div className="h-3 shrink-0" />
              )}
              <div className={`flex min-h-0 flex-col ${showBody ? 'flex-1' : ''}`}>
                <button
                  type="button"
                  onClick={() => setResultsOpen((o) => !o)}
                  className="flex w-full shrink-0 items-center justify-between rounded-xl border border-line bg-card px-3 py-2 text-xs font-medium text-muted shadow-sm hover:text-ink"
                  aria-expanded={resultsOpen}
                >
                  Results: chart &amp; table
                  <ChevronIcon
                    width={14}
                    height={14}
                    className={`transition-transform ${resultsOpen ? '' : '-rotate-90'}`}
                  />
                </button>
                {showBody && (
                  <div ref={resultsRef} className="mt-2 flex min-h-0 flex-1 overflow-hidden">
                    {chart && (
                      <div
                        className="min-w-0"
                        style={table ? { width: `${chartFrac * 100}%` } : { flex: 1 }}
                      >
                        <ChartCard chart={chart} />
                      </div>
                    )}
                    {chart && table && (
                      <Splitter
                        orientation="vertical"
                        containerRef={resultsRef}
                        onChange={setChartFrac}
                        current={chartFrac}
                        label="Resize chart and table"
                      />
                    )}
                    {table && (
                      <div className="min-w-0 flex-1">
                        <ResultTable table={table} />
                      </div>
                    )}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </main>
      <footer className="px-4 pb-2 text-[11px] text-muted">
        Datenquelle: Marktstammdatenregister (Bundesnetzagentur), dl-de/by-2-0 · © BKG 2025,
        dl-de/by-2-0 · Map © OpenStreetMap contributors
        {snapshot && <> · Data snapshot: {snapshot}</>}
      </footer>
    </div>
  )
}
