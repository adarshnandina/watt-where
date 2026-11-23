import { useState } from 'react'
import type { ToolCall } from '../hooks/useChat'

const ICONS: Record<string, string> = {
  find_municipality: '📍',
  capacity_summary: '🔎',
  rank_municipalities: '🏆',
  units_near: '🗺️',
  capacity_timeseries: '📈',
  run_readonly_sql: '🛢️',
}

/** One inline chip per tool call: this is the visible "agent at work" part of the UI. */
export function ToolCallChip({ call }: { call: ToolCall }) {
  const [open, setOpen] = useState(false) // local UI state: is the JSON input expanded?
  const color =
    call.status === 'error'
      ? 'border-red-200 bg-red-50 text-red-700'
      : 'border-slate-200 bg-slate-50 text-slate-700'
  return (
    <div className={`rounded-md border px-2 py-1 text-xs ${color}`}>
      <button
        type="button"
        className="flex w-full items-center gap-1.5 text-left"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        {call.status === 'pending' ? (
          <span
            className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600"
            aria-label="running"
          />
        ) : (
          <span>{ICONS[call.name] ?? '🔧'}</span>
        )}
        <span className="font-mono font-medium">{call.name}</span>
        {call.summary && <span className="truncate">: {call.summary}</span>}
        {call.durationMs !== undefined && (
          <span className="ml-auto shrink-0 text-slate-400">({call.durationMs} ms)</span>
        )}
      </button>
      {open && (
        <pre className="mt-1 overflow-x-auto rounded bg-white/70 p-1.5 text-[11px] text-slate-600">
          {JSON.stringify(call.input, null, 2)}
        </pre>
      )}
    </div>
  )
}
