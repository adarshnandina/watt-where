"""The agent loop: stream the model's answer, run the tools it asks for, feed results back, repeat.

`run_agent` is an async generator of (event_type, data) tuples (see events.py). It is
deliberately independent of Django views and of the real Anthropic client so it can be
tested with a scripted fake client.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

import anthropic
from asgiref.sync import sync_to_async
from django.conf import settings
from django.db import connections

from energy.tools import REGISTRY, anthropic_tool_definitions, call_tool
from energy.tools.base import error

from . import events as ev

log = logging.getLogger("wattwhere.agent")

MAX_TOOL_ROUNDS = 8
MAX_TOKENS = 2048
RETRY_BACKOFF_SECONDS = 1.5

ToolRunner = Callable[[str, dict], Awaitable[tuple[Any, int]]]  # (name, input) -> (ToolResult, ms)


def make_client() -> anthropic.AsyncAnthropic | None:
    if not settings.ANTHROPIC_API_KEY or settings.ANTHROPIC_API_KEY.startswith("sk-ant-..."):
        return None
    return anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)


def _run_tool_sync(name: str, arguments: dict):
    try:
        return call_tool(name, arguments)
    finally:
        connections.close_all()  # this runs in a worker thread with its own DB connection


async def default_tool_runner(name: str, arguments: dict):
    # thread_sensitive=False: independent tool calls really run in parallel threads
    return await sync_to_async(_run_tool_sync, thread_sensitive=False)(name, arguments)


def _block_to_param(block) -> dict:
    """Convert a response content block into the dict form the API accepts back."""
    if block.type == "text":
        return {"type": "text", "text": block.text}
    if block.type == "tool_use":
        return {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
    # thinking / redacted_thinking (and any future block type): the API requires these to be sent back
    # unchanged, signature included, when continuing after a tool call.
    return block.model_dump(exclude_none=True)


def _classify(exc: Exception) -> tuple[str, bool, bool]:
    """-> (user-facing message, retryable-by-user, worth-an-automatic-retry). Never leaks details."""
    if isinstance(exc, anthropic.AuthenticationError | anthropic.PermissionDeniedError):
        return "The server is not configured with a valid API key.", False, False
    if isinstance(exc, anthropic.RateLimitError):
        return "The AI service is rate-limiting requests. Please retry in a moment.", True, True
    if isinstance(exc, anthropic.APIConnectionError | anthropic.APITimeoutError):
        return "Could not reach the AI service. Please retry.", True, True
    if isinstance(exc, anthropic.APIStatusError):
        busy = exc.status_code in (429, 500, 502, 503, 504, 529)
        return (
            ("The AI service is overloaded. Please retry." if busy else "The AI service rejected the request."),
            busy,
            busy,
        )
    return "Something went wrong while answering.", False, False


async def run_agent(
    messages: list[dict],
    system_prompt: str,
    client: Any,
    tool_runner: ToolRunner = default_tool_runner,
    model: str | None = None,
    max_rounds: int = MAX_TOOL_ROUNDS,
    backoff: float = RETRY_BACKOFF_SECONDS,
    known_tools: set[str] | frozenset[str] = frozenset(REGISTRY),
) -> AsyncIterator[ev.Event]:
    started = time.monotonic()
    model = model or settings.ANTHROPIC_MODEL
    msg_id = f"msg_{uuid.uuid4().hex[:16]}"
    yield ev.message_start(msg_id)

    convo = [{"role": m["role"], "content": m["content"]} for m in messages]
    system = [{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}]
    tools = anthropic_tool_definitions()  # last tool carries cache_control -> tools+system are cached
    usage = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0}
    tools_log: list[dict] = []
    stop_reason = "end_turn"
    question = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")

    try:
        for round_no in range(max_rounds + 1):
            final = None
            failed = False
            for attempt in (1, 2):
                emitted = False
                try:
                    async with client.messages.stream(
                        model=model, max_tokens=MAX_TOKENS, system=system, tools=tools, messages=convo
                    ) as stream:
                        async for chunk in stream.text_stream:
                            emitted = True
                            yield ev.text_delta(chunk)
                        final = await stream.get_final_message()
                    break
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    message, retryable, auto_retry = _classify(exc)
                    log.warning("anthropic error (%s), attempt %d", type(exc).__name__, attempt)
                    if attempt == 1 and auto_retry and not emitted:
                        await asyncio.sleep(backoff)
                        continue
                    yield ev.error(message, retryable)
                    failed = True
                    break

            if failed:
                stop_reason = "error"
                break

            usage["input_tokens"] += getattr(final.usage, "input_tokens", 0) or 0
            usage["output_tokens"] += getattr(final.usage, "output_tokens", 0) or 0
            usage["cache_read_input_tokens"] += getattr(final.usage, "cache_read_input_tokens", 0) or 0
            stop_reason = final.stop_reason

            tool_uses = [b for b in final.content if b.type == "tool_use"]
            if final.stop_reason != "tool_use" or not tool_uses:
                break
            if round_no >= max_rounds:
                stop_reason = "max_tool_rounds"
                yield ev.text_delta(
                    "\n\nI reached my limit of tool calls for one question. Please try a narrower or simpler question."
                )
                break

            # A model occasionally invents a tool name. That is a model slip, not something the user should see
            # as a red chip: tell the model (so it can retry) and log it, but emit no UI events for it.
            known = [b for b in tool_uses if b.name in known_tools]
            for b in known:
                yield ev.tool_call(b.id, b.name, b.input)
            # independent tool calls from the same turn run concurrently
            outcomes = await asyncio.gather(*(tool_runner(b.name, dict(b.input)) for b in known))
            by_id = {b.id: o for b, o in zip(known, outcomes, strict=True)}

            result_blocks = []
            for b in tool_uses:
                if b.id in by_id:
                    res, ms = by_id[b.id]
                    yield ev.tool_result(b.id, b.name, res.summary, res.ok, ms)
                    for payload in res.display:  # heavy payloads go to the UI only
                        yield ev.display(b.id, payload)
                else:
                    log.warning("model called unknown tool %r", b.name)
                    res, ms = error(f"Unknown tool '{b.name}'", available=sorted(known_tools)), 0
                tools_log.append(
                    {"name": b.name, "ok": res.ok, "ms": ms, **({} if b.id in by_id else {"unknown": True})}
                )
                result_blocks.append({
                    "type": "tool_result",
                    "tool_use_id": b.id,
                    "content": json.dumps(res.llm_content, ensure_ascii=False, default=str),
                    **({"is_error": True} if not res.ok else {}),
                })  # fmt: skip
            convo.append({"role": "assistant", "content": [_block_to_param(b) for b in final.content]})
            convo.append({"role": "user", "content": result_blocks})
    finally:
        # runs on normal end, error and cancellation (client disconnect)
        log.info(json.dumps({
            "event": "chat_request", "question": question[:300], "tools": tools_log,
            "duration_ms": int((time.monotonic() - started) * 1000), "stop_reason": stop_reason,
            "usage": usage, "model": model,
        }, ensure_ascii=False))  # fmt: skip
    yield ev.message_end(usage, stop_reason)  # skipped on cancellation: nobody is listening
