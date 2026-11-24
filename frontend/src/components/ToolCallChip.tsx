import { useState } from 'react'
import type { ToolCall } from '../hooks/useChat'
import {
  ChartIcon,
  ChevronIcon,
  DatabaseIcon,
  PinIcon,
  ScaleIcon,
  SunIcon,
  TrophyIcon,
} from './icons'

const ICONS: Record<string, typeof SunIcon> = {
  find_municipality: PinIcon,
  capacity_summary: SunIcon,
  rank_municipalities: TrophyIcon,
  units_near: ScaleIcon,
  capacity_timeseries: ChartIcon,
  run_readonly_sql: DatabaseIcon,
}

/** One compact line per tool call: the visible "agent at work" part of the UI. Click to see the input. */
export function ToolCallChip({ call }: { call: ToolCall }) {
  const [open, setOpen] = useState(false) // local UI state: is the JSON input expanded?
  const Icon = ICONS[call.name] ?? DatabaseIcon
  const failed = call.status === 'error'
  return (
    <div
      className={`fade-in rounded-xl border text-xs ${
        failed
          ? 'border-red-200 bg-red-50 text-red-700 dark:border-red-900 dark:bg-red-950/50 dark:text-red-300'
          : 'border-line bg-card text-muted'
      }`}
    >
      <button
        type="button"
        className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        {call.status === 'pending' ? (
          <span
            className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-line border-t-accent"
            role="status"
            aria-label="running"
          />
        ) : (
          <Icon className={failed ? 'text-red-500' : 'text-accent'} />
        )}
        <span className="font-mono text-[11px] font-medium text-ink">{call.name}</span>
        {call.summary && <span className="min-w-0 truncate">{call.summary}</span>}
        <span className="ml-auto flex shrink-0 items-center gap-1.5">
          {call.durationMs !== undefined && (
            <span className="text-[11px] opacity-70">{call.durationMs} ms</span>
          )}
          <ChevronIcon
            width={12}
            height={12}
            className={`transition-transform ${open ? 'rotate-180' : ''}`}
          />
        </span>
      </button>
      {open && (
        <pre className="mx-2.5 mb-2 overflow-x-auto rounded-lg bg-page p-2 text-[11px] text-muted">
          {JSON.stringify(call.input, null, 2)}
        </pre>
      )}
    </div>
  )
}
