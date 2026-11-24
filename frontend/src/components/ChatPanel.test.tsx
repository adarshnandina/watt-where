// Render tests: these exist because a missing button once slipped through while the reducer tests were green.
import { renderToString } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { ChatMessage } from '../hooks/useChat'
import { ChatPanel } from './ChatPanel'

const noop = () => {}
const props = {
  messages: [] as ChatMessage[],
  isStreaming: false,
  error: null,
  draft: '',
  onDraftChange: noop,
  onSend: noop,
  onStop: noop,
  onRetry: noop,
  onDismissError: noop,
  onNewChat: noop,
}
const msg = (over: Partial<ChatMessage>): ChatMessage => ({
  id: 'm',
  role: 'assistant',
  text: '',
  toolCalls: [],
  displays: [],
  streaming: false,
  ...over,
})

describe('ChatPanel', () => {
  it('always renders the New chat button and the composer', () => {
    const html = renderToString(<ChatPanel {...props} />)
    expect(html).toContain('New chat')
    expect(html).toContain('aria-label="Your question"')
    expect(html).toContain('What would you like to know?') // empty-state greeting
  })

  const newChatTag = (html: string) =>
    html.match(/<button[^>]*title="Clear this conversation[^>]*>/)?.[0] ?? ''

  it('disables New chat when there is nothing to clear, and enables it once there is a conversation', () => {
    expect(newChatTag(renderToString(<ChatPanel {...props} />))).toContain('disabled=""')
    const html = renderToString(
      <ChatPanel {...props} messages={[msg({ role: 'user', text: 'Hi' })]} />,
    )
    expect(html).not.toContain('What would you like to know?')
    expect(newChatTag(html)).not.toBe('')
    expect(newChatTag(html)).not.toContain('disabled=""')
  })

  it('has a theme toggle (light by default) and the New chat button next to it', () => {
    const html = renderToString(<ChatPanel {...props} />)
    expect(html).toContain('aria-label="Switch to dark mode"')
  })

  it('shows Stop instead of Send while streaming, plus a tool chip and a thinking indicator', () => {
    const streaming = msg({
      streaming: true,
      toolCalls: [{ id: 't', name: 'capacity_summary', input: {}, status: 'pending' }],
    })
    const html = renderToString(
      <ChatPanel {...props} isStreaming messages={[msg({ role: 'user', text: 'Q' }), streaming]} />,
    )
    expect(html).toContain('aria-label="Stop"')
    expect(html).not.toContain('aria-label="Send"')
    expect(html).toContain('capacity_summary')
    expect(html).toContain('aria-label="Thinking"')
  })

  it('renders an error banner with Retry when the error is retryable', () => {
    const html = renderToString(
      <ChatPanel {...props} error={{ message: 'Busy', retryable: true }} />,
    )
    expect(html).toContain('Busy')
    expect(html).toContain('Retry')
  })
})
