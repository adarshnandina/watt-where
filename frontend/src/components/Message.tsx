import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { ChatMessage } from '../hooks/useChat'
import { ToolCallChip } from './ToolCallChip'

export function Message({ message }: { message: ChatMessage }) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-slate-800 px-3.5 py-2 text-sm text-white">
          {message.text}
        </div>
      </div>
    )
  }
  const waiting = message.streaming && message.text === '' && message.toolCalls.length === 0
  return (
    <div className="flex flex-col gap-2">
      {message.toolCalls.map((c) => (
        <ToolCallChip key={c.id} call={c} />
      ))}
      {(message.text !== '' || waiting) && (
        <div className="md max-w-[95%] text-sm leading-relaxed">
          {/* react-markdown turns the model's markdown into elements as the text grows */}
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.text}</ReactMarkdown>
          {message.streaming && <span className="cursor-blink" aria-hidden />}
        </div>
      )}
    </div>
  )
}
