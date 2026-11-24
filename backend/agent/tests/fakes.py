"""A scripted stand-in for AsyncAnthropic: no network, no API key."""

import asyncio
from types import SimpleNamespace as NS

import anthropic
import httpx2 as httpx

from energy.tools.base import ToolResult


def text_block(t):
    return NS(type="text", text=t)


def tool_block(id, name, input=None):
    return NS(type="tool_use", id=id, name=name, input=input or {})


def round_(chunks=(), blocks=None, stop="end_turn", usage=None):
    blocks = blocks if blocks is not None else [text_block("".join(chunks))]
    return NS(chunks=list(chunks), message=NS(
        content=blocks, stop_reason=stop,
        usage=NS(input_tokens=100, output_tokens=20, cache_read_input_tokens=80, **(usage or {})),
    ))  # fmt: skip


class FakeStream:
    def __init__(self, script, owner):
        self.script, self.owner = script, owner

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        self.owner.closed += 1
        return False

    @property
    def text_stream(self):
        async def gen():
            if self.script is HANG:
                await asyncio.Event().wait()  # never finishes: simulates a slow model
            for c in self.script.chunks:
                yield c

        return gen()  # fmt: skip

    async def get_final_message(self):
        return self.script.message


HANG = object()


class FakeClient:
    """`rounds` is consumed one item per messages.stream() call; an Exception item is raised."""

    def __init__(self, rounds, repeat_last=False):
        self.rounds, self.repeat_last = list(rounds), repeat_last
        self.calls: list[dict] = []
        self.closed = 0
        self.messages = NS(stream=self._stream)

    def _stream(self, **kwargs):
        self.calls.append(kwargs)
        item = self.rounds[0] if (self.repeat_last and len(self.rounds) == 1) else self.rounds.pop(0)
        if isinstance(item, Exception):
            raise item
        return FakeStream(item, self)


def api_error(cls, status):
    req = httpx.Request("POST", "http://test")
    return cls("boom", response=httpx.Response(status, request=req), body=None)


rate_limit = lambda: api_error(anthropic.RateLimitError, 429)  # noqa: E731
auth_error = lambda: api_error(anthropic.AuthenticationError, 401)  # noqa: E731


class FakeTools:
    """Records calls; returns a canned ToolResult with a big display payload and small llm_content."""

    def __init__(self, delay=0.0, ok=True):
        self.calls, self.delay, self.ok = [], delay, ok

    async def __call__(self, name, arguments):
        self.calls.append((name, arguments))
        await asyncio.sleep(self.delay)
        if not self.ok:
            return ToolResult({"error": "nope"}, [], "Error: nope"), 5
        return ToolResult(
            {"total_mw": 1.5}, [{"kind": "table", "title": "t", "columns": ["a"], "rows": [[1]]}], "Found 3 units"
        ), 12  # fmt: skip


def thinking_block(text="hmm", signature="sig123"):
    data = {"type": "thinking", "thinking": text, "signature": signature}
    return NS(**data, model_dump=lambda exclude_none=True: dict(data))
