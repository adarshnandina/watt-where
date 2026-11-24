import type { ChatError, ChatMessage } from '../hooks/useChat'
import { Composer } from './Composer'
import { ExampleQuestions } from './ExampleQuestions'
import { useTheme } from '../lib/theme'
import { BoltIcon, MoonIcon, PlusIcon, SunIcon } from './icons'
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
  const { theme, toggle } = useTheme()
  const send = () => {
    p.onSend(p.draft)
    p.onDraftChange('')
  }
  return (
    <section className="flex h-full min-h-0 flex-col">
      <header className="flex h-14 shrink-0 items-center justify-between gap-2 px-4">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent text-white">
            <BoltIcon width={15} height={15} />
          </div>
          <h1 className="text-[17px] font-semibold tracking-tight">WattWhere</h1>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={toggle}
            aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
            title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-line bg-card text-muted shadow-sm hover:text-ink"
          >
            {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
          </button>
          <button
            type="button"
            onClick={p.onNewChat}
            disabled={p.messages.length === 0 && p.draft === ''}
            title="Clear this conversation and start a new one"
            className="flex items-center gap-1.5 whitespace-nowrap rounded-lg border border-line bg-card px-3 py-1.5 text-sm font-medium shadow-sm hover:bg-bubble disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-card"
          >
            <PlusIcon width={15} height={15} />
            New chat
          </button>
        </div>
      </header>

      {p.messages.length === 0 ? (
        <ExampleQuestions onPick={p.onSend} />
      ) : (
        <MessageList messages={p.messages} />
      )}

      {p.error && (
        <div className="px-4">
          <div
            role="alert"
            className="mx-auto mb-2 flex max-w-3xl items-center gap-2 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/50 dark:text-red-200"
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
