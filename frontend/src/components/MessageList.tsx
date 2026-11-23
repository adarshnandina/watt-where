import { useEffect, useRef } from 'react'
import type { ChatMessage } from '../hooks/useChat'
import { Message } from './Message'

export function MessageList({ messages }: { messages: ChatMessage[] }) {
  // useEffect runs after rendering. Here: scroll the newest content into view as text streams in.
  const endRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [messages])

  return (
    <div className="flex flex-1 flex-col gap-4 overflow-y-auto px-4 py-4">
      {messages.map((m) => (
        <Message key={m.id} message={m} />
      ))}
      <div ref={endRef} />
    </div>
  )
}
