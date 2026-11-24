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
      <header className="flex items-start justify-between gap-2 border-b border-slate-200 px-4 py-3">
        <div className="min-w-0">
          <h1 className="text-lg font-semibold">⚡ WattWhere</h1>
          <p className="text-xs text-slate-500">
            Ask questions about the energy transition in Baden-Württemberg, answered from official
            data.
          </p>
        </div>
        <button
          type="button"
          onClick={p.onNewChat}
          disabled={p.messages.length === 0 && p.draft === ''}
          title="Clear this conversation and start a new one"
          className="shrink-0 whitespace-nowrap rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-40"
        >
          ＋ New chat
        </button>
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
