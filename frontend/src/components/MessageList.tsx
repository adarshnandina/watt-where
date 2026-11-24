import { useEffect, useRef } from 'react'
import type { ChatMessage } from '../hooks/useChat'
import { Message } from './Message'

export function MessageList({ messages }: { messages: ChatMessage[] }) {
  // useEffect runs after rendering. Here: keep the newest content in view as text streams in.
  const endRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [messages])

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-7 px-5 py-6">
        {messages.map((m) => (
          <Message key={m.id} message={m} />
        ))}
        <div ref={endRef} />
      </div>
    </div>
  )
}
