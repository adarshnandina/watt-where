import { useLayoutEffect, useRef } from 'react'
import type { KeyboardEvent } from 'react'
import { ArrowUpIcon, StopIcon } from './icons'

interface Props {
  value: string
  onChange: (v: string) => void
  onSend: () => void
  onStop: () => void
  isStreaming: boolean
}

const MAX_HEIGHT = 200

export function Composer({ value, onChange, onSend, onStop, isStreaming }: Props) {
  const ref = useRef<HTMLTextAreaElement>(null)

  // Auto-grow: reset to "auto" so it can also shrink, then fit the content (up to a maximum).
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT)}px`
  }, [value])

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter sends, Shift+Enter inserts a newline. (isComposing: don't send while typing with an IME)
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      if (!isStreaming && value.trim() !== '') onSend()
    }
  }
  const canSend = value.trim() !== ''
  return (
    <div className="px-4 pb-3 pt-2">
      <div className="mx-auto max-w-3xl">
        <div className="flex items-end gap-2 rounded-3xl border border-line bg-card py-2 pl-5 pr-2 shadow-sm transition-shadow focus-within:border-stone-300 focus-within:shadow-md">
          <textarea
            ref={ref}
            className="max-h-[200px] min-h-[28px] flex-1 resize-none self-center bg-transparent py-1 text-[15px] leading-6 outline-none placeholder:text-stone-400 disabled:opacity-60"
            rows={1}
            placeholder="Ask about solar, wind, storage in Baden-Württemberg…"
            value={value}
            disabled={isStreaming}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={onKeyDown}
            aria-label="Your question"
          />
          {isStreaming ? (
            <button
              type="button"
              onClick={onStop}
              aria-label="Stop"
              title="Stop generating"
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-ink text-white hover:bg-stone-700"
            >
              <StopIcon width={14} height={14} />
            </button>
          ) : (
            <button
              type="button"
              onClick={onSend}
              disabled={!canSend}
              aria-label="Send"
              title="Send (Enter)"
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent text-white transition-opacity hover:opacity-90 disabled:bg-stone-200 disabled:text-stone-400"
            >
              <ArrowUpIcon width={18} height={18} />
            </button>
          )}
        </div>
        <p className="mt-2 text-center text-[11px] text-muted">
          Answers come from official registry data and tools, but can still be wrong. Check
          important figures.
        </p>
      </div>
    </div>
  )
}
