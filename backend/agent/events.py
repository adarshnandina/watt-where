"""The SSE event protocol. Defined once here; mirrored in frontend/src/api/types.ts.

Wire format of one message:   event: <type>\\ndata: <json>\\n\\n
Types: message_start, text_delta, tool_call, tool_result, display, error, message_end.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

Event = tuple[str, dict[str, Any]]  # (type, data)

EVENT_TYPES = ("message_start", "text_delta", "tool_call", "tool_result", "display", "error", "message_end")

HEARTBEAT_INTERVAL = 15.0


def message_start(id: str) -> Event:
    return "message_start", {"id": id}


def text_delta(text: str) -> Event:
    return "text_delta", {"text": text}


def tool_call(id: str, name: str, input: dict) -> Event:
    return "tool_call", {"id": id, "name": name, "input": input}


def tool_result(id: str, name: str, summary: str, ok: bool, duration_ms: int) -> Event:
    return "tool_result", {"id": id, "name": name, "summary": summary, "ok": ok, "duration_ms": duration_ms}


def display(tool_call_id: str, payload: dict) -> Event:
    return "display", {"tool_call_id": tool_call_id, "payload": payload}


def error(message: str, retryable: bool) -> Event:
    return "error", {"message": message, "retryable": retryable}


def message_end(usage: dict, stop_reason: str) -> Event:
    return "message_end", {"usage": usage, "stop_reason": stop_reason}


def encode(event: Event) -> str:
    etype, data = event
    return f"event: {etype}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


HEARTBEAT = ": ping\n\n"  # SSE comment line: ignored by clients, keeps proxies from timing out


async def with_heartbeat(events: AsyncIterator[Event], interval: float = HEARTBEAT_INTERVAL) -> AsyncIterator[str]:
    """Encode events as SSE text and emit a ping comment whenever `interval` seconds pass silently.

    The agent runs in its own task and pushes into a queue, so a slow tool call can't block
    the heartbeat. If the consumer goes away (client disconnect -> cancellation/GeneratorExit),
    the `finally` cancels the agent task, which stops the LLM stream and any further tool rounds.
    """
    queue: asyncio.Queue = asyncio.Queue()
    done = object()

    async def pump() -> None:
        try:
            async for ev in events:
                await queue.put(ev)
        finally:
            await queue.put(done)

    task = asyncio.create_task(pump())
    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=interval)
            except TimeoutError:
                yield HEARTBEAT
                continue
            if item is done:
                break
            yield encode(item)
    finally:
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
