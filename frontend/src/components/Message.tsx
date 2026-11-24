import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { ChatMessage } from '../hooks/useChat'
import { BoltIcon, CheckIcon, CopyIcon } from './icons'
import { ToolCallChip } from './ToolCallChip'

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    void navigator.clipboard?.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }
  return (
    <button
      type="button"
      onClick={copy}
      className="flex items-center gap-1 rounded-md px-1.5 py-1 text-xs text-muted hover:bg-bubble hover:text-ink"
      aria-label="Copy answer"
    >
      {copied ? <CheckIcon width={14} height={14} /> : <CopyIcon width={14} height={14} />}
      {copied ? 'Copied' : 'Copy'}
    </button>
  )
}

export function Message({ message }: { message: ChatMessage }) {
  if (message.role === 'user') {
    return (
      <div className="fade-in flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap rounded-3xl bg-bubble px-4 py-2.5 text-[15px] leading-relaxed">
          {message.text}
        </div>
      </div>
    )
  }
  const waiting = message.streaming && message.text === ''
  return (
    <div className="fade-in flex gap-3">
      <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent text-white">
        <BoltIcon width={14} height={14} />
      </div>
      <div className="min-w-0 flex-1">
        {message.toolCalls.length > 0 && (
          <div className="mb-3 flex flex-col gap-1.5">
            {message.toolCalls.map((c) => (
              <ToolCallChip key={c.id} call={c} />
            ))}
          </div>
        )}
        {waiting && (
          <div className="dots py-2" role="status" aria-label="Thinking">
            <span />
            <span />
            <span />
          </div>
        )}
        {message.text !== '' && (
          <div className="md text-[15px]">
            {/* react-markdown turns the model's markdown into elements as the text grows */}
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.text}</ReactMarkdown>
            {message.streaming && <span className="cursor-blink" aria-hidden />}
          </div>
        )}
        {!message.streaming && message.text !== '' && (
          <div className="mt-1.5 -ml-1.5">
            <CopyButton text={message.text} />
          </div>
        )}
      </div>
    </div>
  )
}
