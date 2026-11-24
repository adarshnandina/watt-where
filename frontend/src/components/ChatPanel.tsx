import type { ChatError, ChatMessage } from '../hooks/useChat'
import { Composer } from './Composer'
import { ExampleQuestions } from './ExampleQuestions'
import { MessageList } from './MessageList'

interface Props {
  messages: ChatMessage[]
  isStreaming: boolean
  error: ChatError | null
  draft: string
  onDraftChange: (v: string) => void
  onSend: (text: string) => void
  onStop: () => void
  onRetry: () => void
  onDismissError: () => void
  onNewChat: () => void
}

export function ChatPanel(p: Props) {
  const send = () => {
    p.onSend(p.draft)
    p.onDraftChange('')
  }
  return (
    <section className="flex h-full min-h-0 flex-col bg-white">
      <header className="border-b border-slate-200 px-4 py-3">
        <h1 className="text-lg font-semibold">⚡ WattWhere</h1>
        <p className="text-xs text-slate-500">
          Ask questions about the energy transition in Baden-Württemberg, answered from official
          data.
        </p>
      </header>

      {p.messages.length === 0 ? (
        <ExampleQuestions onPick={p.onSend} />
      ) : (
        <MessageList messages={p.messages} />
      )}

      {p.error && (
        <div
          role="alert"
          className="mx-3 mb-2 flex items-center gap-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800"
        >
          <span className="flex-1">{p.error.message}</span>
          {p.error.retryable && (
            <button type="button" onClick={p.onRetry} className="font-medium underline">
              Retry
            </button>
          )}
          <button
            type="button"
            onClick={p.onDismissError}
            aria-label="Dismiss"
            className="text-red-500"
          >
            ✕
          </button>
        </div>
      )}

      <Composer
        value={p.draft}
        onChange={p.onDraftChange}
        onSend={send}
        onStop={p.onStop}
        isStreaming={p.isStreaming}
      />
    </section>
  )
}
