import asyncio
import json
import time

import pytest

from agent import events as ev
from agent.loop import run_agent

from .fakes import HANG, FakeClient, FakeTools, auth_error, rate_limit, round_, text_block, tool_block

MSGS = [{"role": "user", "content": "How much solar in Freiburg?"}]


async def collect(client, tools=None, **kw):
    tools = tools or FakeTools()
    out = [e async for e in run_agent(MSGS, "SYSTEM", client, tool_runner=tools, backoff=0, **kw)]
    return out, tools


def types(events):
    return [t for t, _ in events]


async def test_plain_text_answer():
    client = FakeClient([round_(["Hel", "lo"])])
    events, _ = await collect(client)
    assert types(events) == ["message_start", "text_delta", "text_delta", "message_end"]
    end = events[-1][1]
    assert end["stop_reason"] == "end_turn"
    assert end["usage"] == {"input_tokens": 100, "output_tokens": 20, "cache_read_input_tokens": 80}


async def test_tool_round_event_order_and_what_the_model_sees():
    tool_use = [tool_block("t1", "capacity_summary", {"area": "region"})]
    client = FakeClient(
        [round_(["Checking. "], [text_block("Checking. ")] + tool_use, stop="tool_use"), round_(["Done."])]
    )
    events, tools = await collect(client)
    assert types(events) == [
        "message_start", "text_delta", "tool_call", "tool_result", "display", "text_delta", "message_end",
    ]  # fmt: skip
    assert events[2][1] == {"id": "t1", "name": "capacity_summary", "input": {"area": "region"}}
    assert events[3][1] == {
        "id": "t1",
        "name": "capacity_summary",
        "summary": "Found 3 units",
        "ok": True,
        "duration_ms": 12,
    }
    assert events[4][1]["tool_call_id"] == "t1" and events[4][1]["payload"]["kind"] == "table"
    assert tools.calls == [("capacity_summary", {"area": "region"})]
    # the second API call carries the compact llm_content, NOT the display payload
    second = client.calls[1]["messages"]
    assert second[-1]["role"] == "user"
    block = second[-1]["content"][0]
    assert block["type"] == "tool_result" and block["tool_use_id"] == "t1"
    assert json.loads(block["content"]) == {"total_mw": 1.5} and "rows" not in block["content"]
    assert second[-2]["role"] == "assistant" and second[-2]["content"][1]["type"] == "tool_use"


async def test_prompt_caching_markers_and_model_are_sent():
    client = FakeClient([round_(["x"])])
    await collect(client, model="test-model")
    call = client.calls[0]
    assert call["model"] == "test-model"
    assert call["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert call["tools"][-1]["cache_control"] == {"type": "ephemeral"}
    assert len(call["tools"]) == 6


async def test_tool_round_limit_stops_gracefully():
    looping = round_([], [tool_block("t", "capacity_summary", {"area": "region"})], stop="tool_use")
    client = FakeClient([looping], repeat_last=True)
    events, tools = await collect(client, max_rounds=3)
    assert len(tools.calls) == 3 and len(client.calls) == 4
    assert events[-1][1]["stop_reason"] == "max_tool_rounds"
    assert "limit" in "".join(d["text"] for t, d in events if t == "text_delta")


async def test_default_limit_is_eight_rounds():
    looping = round_([], [tool_block("t", "find_municipality", {"query": "x"})], stop="tool_use")
    client = FakeClient([looping], repeat_last=True)
    _, tools = await collect(client)
    assert len(tools.calls) == 8


async def test_parallel_tool_calls_run_concurrently():
    blocks = [tool_block(f"t{i}", "capacity_summary", {"area": "region"}) for i in range(3)]
    client = FakeClient([round_([], blocks, stop="tool_use"), round_(["ok"])])
    t0 = time.monotonic()
    events, tools = await collect(client, FakeTools(delay=0.2))
    assert time.monotonic() - t0 < 0.5  # 3 x 0.2s sequentially would be 0.6s
    assert types(events).count("tool_call") == 3 and types(events).count("tool_result") == 3
    assert len(client.calls[1]["messages"][-1]["content"]) == 3


async def test_failed_tool_is_reported_and_marked_error_for_the_model():
    client = FakeClient([round_([], [tool_block("t1", "x")], stop="tool_use"), round_(["sorry"])])
    events, _ = await collect(client, FakeTools(ok=False))
    assert [d["ok"] for t, d in events if t == "tool_result"] == [False]
    assert client.calls[1]["messages"][-1]["content"][0]["is_error"] is True
    assert events[-1][1]["stop_reason"] == "end_turn"  # conversation continues


async def test_rate_limit_is_retried_once():
    client = FakeClient([rate_limit(), round_(["fine"])])
    events, _ = await collect(client)
    assert "error" not in types(events) and len(client.calls) == 2


async def test_persistent_rate_limit_emits_retryable_error():
    client = FakeClient([rate_limit(), rate_limit()])
    events, _ = await collect(client)
    assert types(events) == ["message_start", "error", "message_end"]
    assert events[1][1]["retryable"] is True and "boom" not in events[1][1]["message"]
    assert events[-1][1]["stop_reason"] == "error"


async def test_auth_error_not_retried_and_no_leak():
    client = FakeClient([auth_error(), round_(["never"])])
    events, _ = await collect(client)
    assert len(client.calls) == 1
    err = events[1][1]
    assert err["retryable"] is False and "key" in err["message"].lower() and "boom" not in err["message"]


async def test_client_disconnect_stops_stream_and_further_tools():
    client = FakeClient([HANG])
    tools = FakeTools()
    gen = run_agent(MSGS, "S", client, tool_runner=tools)

    async def consume():
        async for _ in gen:
            pass

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert client.closed == 1  # the LLM stream context was closed
    assert tools.calls == []


async def test_cancel_during_tool_execution_via_heartbeat_wrapper():
    """The SSE wrapper cancels the agent when the consumer goes away; no more LLM rounds follow."""
    client = FakeClient([round_([], [tool_block("t", "x")], stop="tool_use"), round_(["late"])])
    tools = FakeTools(delay=10)
    stream = ev.with_heartbeat(run_agent(MSGS, "S", client, tool_runner=tools), interval=5)
    first = await anext(stream)
    assert first.startswith("event: message_start")
    await anext(stream)  # tool_call
    await stream.aclose()  # consumer disconnects while the tool is running
    await asyncio.sleep(0.05)
    assert len(client.calls) == 1  # never asked the model for round two


async def test_heartbeat_ping_emitted_during_silence():
    async def slow():
        yield ev.message_start("m")
        await asyncio.sleep(0.25)
        yield ev.message_end({}, "end_turn")

    out = [chunk async for chunk in ev.with_heartbeat(slow(), interval=0.05)]
    assert out[0].startswith("event: message_start")
    assert out.count(": ping\n\n") >= 2
    assert out[-1].startswith("event: message_end")


def test_encode_framing():
    s = ev.encode(ev.text_delta("Grüße\nzwei"))
    assert s == 'event: text_delta\ndata: {"text": "Grüße\\nzwei"}\n\n'
