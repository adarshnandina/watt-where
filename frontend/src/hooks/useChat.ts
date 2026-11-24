// useChat: all of the chat's state and behaviour in one place.
//
// React concepts used here (for the reader new to React):
//  - A *hook* is a function whose name starts with "use"; it lets a component keep state.
//  - `useReducer(reducer, initial)` keeps state that changes through named *actions*. The reducer
//    is a pure function (state, action) => newState. It must never modify `state` in place;
//    it returns a fresh object, which is how React notices something changed and re-renders.
//    We use a reducer rather than many `useState`s because one streamed event often changes
//    several things at once (e.g. a tool finishing updates its chip *and* may add a display).
//  - Because the reducer is a pure function it is easy to unit-test (see useChat.test.ts).

import { useCallback, useReducer, useRef } from 'react'
import { streamChat } from '../api/sse'
import type { ChatEvent, DisplayPayload, HistoryMessage } from '../api/types'

export interface ToolCall {
  id: string
  name: string
  input: Record<string, unknown>
  status: 'pending' | 'ok' | 'error'
  summary?: string
  durationMs?: number
}

export interface DisplayItem {
  toolCallId: string
  payload: DisplayPayload
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  text: string
  toolCalls: ToolCall[] // only for assistant messages
  displays: DisplayItem[] // map layers / charts / tables produced by tools
  streaming: boolean // true while this assistant message is still arriving
}

export interface ChatError {
  message: string
  retryable: boolean
}

export interface ChatState {
  messages: ChatMessage[]
  isStreaming: boolean
  error: ChatError | null
}

export const initialState: ChatState = { messages: [], isStreaming: false, error: null }

// Every way the state can change. A discriminated union: `type` tells TypeScript which other
// fields exist, so the compiler checks we handle each case correctly.
export type ChatAction =
  | { type: 'send'; userId: string; assistantId: string; text: string }
  | { type: 'event'; event: ChatEvent }
  | { type: 'finish' } // stream ended (normally, or because the user pressed Stop)
  | { type: 'fail'; message: string } // network/HTTP failure (not an `error` event from the server)
  | { type: 'dismiss_error' }
  | { type: 'reset' } // New chat: forget everything
  | { type: 'drop_last_turn' } // removes the last user message + its assistant reply (used by retry)

function updateLastAssistant(
  messages: ChatMessage[],
  change: (m: ChatMessage) => ChatMessage,
): ChatMessage[] {
  const i = messages.length - 1
  if (i < 0 || messages[i].role !== 'assistant') return messages
  return [...messages.slice(0, i), change(messages[i])]
}

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case 'send':
      return {
        messages: [
          ...state.messages,
          {
            id: action.userId,
            role: 'user',
            text: action.text,
            toolCalls: [],
            displays: [],
            streaming: false,
          },
          // An empty assistant message that the stream will fill in.
          {
            id: action.assistantId,
            role: 'assistant',
            text: '',
            toolCalls: [],
            displays: [],
            streaming: true,
          },
        ],
        isStreaming: true,
        error: null,
      }

    case 'event': {
      const e = action.event
      switch (e.type) {
        case 'text_delta':
          return {
            ...state,
            messages: updateLastAssistant(state.messages, (m) => ({ ...m, text: m.text + e.text })),
          }
        case 'tool_call':
          return {
            ...state,
            messages: updateLastAssistant(state.messages, (m) => ({
              ...m,
              toolCalls: [
                ...m.toolCalls,
                { id: e.id, name: e.name, input: e.input, status: 'pending' },
              ],
            })),
          }
        case 'tool_result':
          return {
            ...state,
            messages: updateLastAssistant(state.messages, (m) => ({
              ...m,
              toolCalls: m.toolCalls.map((t) =>
                t.id === e.id
                  ? {
                      ...t,
                      status: e.ok ? 'ok' : 'error',
                      summary: e.summary,
                      durationMs: e.duration_ms,
                    }
                  : t,
              ),
            })),
          }
        case 'display':
          return {
            ...state,
            messages: updateLastAssistant(state.messages, (m) => ({
              ...m,
              displays: [...m.displays, { toolCallId: e.tool_call_id, payload: e.payload }],
            })),
          }
        case 'error':
          return { ...state, error: { message: e.message, retryable: e.retryable } }
        case 'message_end':
          return {
            ...state,
            isStreaming: false,
            messages: updateLastAssistant(state.messages, (m) => ({ ...m, streaming: false })),
          }
        case 'message_start':
          return state // nothing to show; the assistant message already exists
      }
      return state
    }

    case 'finish':
      return {
        ...state,
        isStreaming: false,
        messages: updateLastAssistant(state.messages, (m) => ({
          ...m,
          streaming: false,
          // A tool that never reported back (e.g. user pressed Stop) must not spin forever.
          toolCalls: m.toolCalls.map((t) =>
            t.status === 'pending' ? { ...t, status: 'error', summary: 'Stopped' } : t,
          ),
        })),
      }

    case 'fail':
      return {
        ...state,
        isStreaming: false,
        error: { message: action.message, retryable: true },
        messages: updateLastAssistant(state.messages, (m) => ({ ...m, streaming: false })),
      }

    case 'reset':
      return initialState

    case 'dismiss_error':
      return { ...state, error: null }

    case 'drop_last_turn': {
      const n = state.messages.length
      const hasTurn =
        n >= 2 &&
        state.messages[n - 1].role === 'assistant' &&
        state.messages[n - 2].role === 'user'
      return hasTurn ? { ...state, messages: state.messages.slice(0, -2), error: null } : state
    }
  }
}

/** The backend is stateless: we send only the visible text of earlier turns. */
export function toHistory(messages: ChatMessage[]): HistoryMessage[] {
  return messages
    .filter((m) => m.text.trim() !== '')
    .map((m) => ({ role: m.role, content: m.text }))
}

let counter = 0
const newId = () => `m${Date.now()}-${counter++}`

export function useChat() {
  const [state, dispatch] = useReducer(chatReducer, initialState)

  // A "ref" is a box that survives re-renders but does NOT trigger one when changed. We keep the
  // AbortController in one so `stop()` can cancel whichever request is currently running.
  const abortRef = useRef<AbortController | null>(null)

  // Run one request against the backend and pump its events into the reducer.
  const run = useCallback(async (history: HistoryMessage[]) => {
    const controller = new AbortController()
    abortRef.current = controller
    try {
      for await (const event of streamChat(history, controller.signal)) {
        dispatch({ type: 'event', event })
      }
      dispatch({ type: 'finish' })
    } catch (err) {
      if (controller.signal.aborted)
        dispatch({ type: 'finish' }) // user pressed Stop: not an error
      else
        dispatch({
          type: 'fail',
          message: err instanceof Error ? err.message : 'Could not reach the server.',
        })
    } finally {
      abortRef.current = null
    }
  }, [])

  const send = useCallback(
    (text: string) => {
      const trimmed = text.trim()
      if (!trimmed || state.isStreaming) return
      dispatch({ type: 'send', userId: newId(), assistantId: newId(), text: trimmed })
      void run([...toHistory(state.messages), { role: 'user', content: trimmed }])
    },
    [run, state.isStreaming, state.messages],
  )

  const stop = useCallback(() => abortRef.current?.abort(), [])

  // Retry = remove the failed turn, then send the same question again.
  const retry = useCallback(() => {
    if (state.isStreaming) return
    const n = state.messages.length
    if (n < 2 || state.messages[n - 2].role !== 'user') return
    const question = state.messages[n - 2].text
    const earlier = state.messages.slice(0, -2)
    dispatch({ type: 'drop_last_turn' })
    dispatch({ type: 'send', userId: newId(), assistantId: newId(), text: question })
    void run([...toHistory(earlier), { role: 'user', content: question }])
  }, [run, state.isStreaming, state.messages])

  // New chat: cancel any running request first (so a late event can't land in the new conversation),
  // then wipe the state.
  const clear = useCallback(() => {
    abortRef.current?.abort()
    dispatch({ type: 'reset' })
  }, [])

  const dismissError = useCallback(() => dispatch({ type: 'dismiss_error' }), [])

  return {
    messages: state.messages,
    isStreaming: state.isStreaming,
    error: state.error,
    send,
    stop,
    retry,
    clear,
    dismissError,
  }
}
