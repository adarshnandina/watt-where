import type { KeyboardEvent } from 'react'

interface Props {
  value: string
  onChange: (v: string) => void
  onSend: () => void
  onStop: () => void
  isStreaming: boolean
}

export function Composer({ value, onChange, onSend, onStop, isStreaming }: Props) {
  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter sends, Shift+Enter inserts a newline. (isComposing: don't send while typing with an IME)
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      if (!isStreaming) onSend()
    }
  }
  return (
    <div className="border-t border-slate-200 bg-white p-3">
      <div className="flex items-end gap-2">
        <textarea
          className="max-h-32 min-h-[2.5rem] flex-1 resize-none rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-slate-500 disabled:bg-slate-50"
          rows={1}
          placeholder="Ask about solar, wind, storage… in Baden-Württemberg"
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
            className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
          >
            Stop
          </button>
        ) : (
          <button
            type="button"
            onClick={onSend}
            disabled={value.trim() === ''}
            className="rounded-lg bg-slate-800 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-40"
          >
            Send
          </button>
        )}
      </div>
      <p className="mt-1 text-[11px] text-slate-400">Enter to send · Shift+Enter for a new line</p>
    </div>
  )
}
