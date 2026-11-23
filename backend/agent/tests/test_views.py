import json

import pytest
from django.test import AsyncClient

from agent import views
from agent.prompts import build_system_prompt

from .fakes import FakeClient, FakeTools, round_

POST = {"content_type": "application/json"}


@pytest.fixture
def fake_llm(monkeypatch):
    client = FakeClient([round_(["Hallo ", "Welt"])])
    monkeypatch.setattr(views, "make_client", lambda: client)
    monkeypatch.setattr(views, "build_system_prompt", lambda: "SYS")
    return client


async def read(response):
    return "".join([c.decode() if isinstance(c, bytes) else c async for c in response.streaming_content])


async def test_chat_streams_sse_with_correct_headers_and_framing(fake_llm):
    r = await AsyncClient().post("/api/chat", json.dumps({"messages": [{"role": "user", "content": "hi"}]}), **POST)
    assert r.status_code == 200
    assert r["Content-Type"].startswith("text/event-stream")
    assert r["Cache-Control"] == "no-cache" and r["X-Accel-Buffering"] == "no"
    body = await read(r)
    frames = [f for f in body.split("\n\n") if f]
    assert [f.split("\n")[0] for f in frames] == [
        "event: message_start", "event: text_delta", "event: text_delta", "event: message_end",
    ]  # fmt: skip
    assert json.loads(frames[1].split("\n")[1].removeprefix("data: ")) == {"text": "Hallo "}


async def test_history_is_capped_and_starts_with_user(fake_llm):
    msgs = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"} for i in range(41)]
    r = await AsyncClient().post("/api/chat", json.dumps({"messages": msgs}), **POST)
    await read(r)
    sent = fake_llm.calls[0]["messages"]
    assert len(sent) <= 20 and sent[0]["role"] == "user" and sent[-1]["content"] == "m40"


async def test_no_api_key_gives_error_event_not_crash(monkeypatch):
    monkeypatch.setattr(views, "make_client", lambda: None)
    r = await AsyncClient().post("/api/chat", json.dumps({"messages": [{"role": "user", "content": "hi"}]}), **POST)
    body = await read(r)
    assert "event: error" in body and "ANTHROPIC_API_KEY" in body and "sk-ant" not in body


@pytest.mark.parametrize(
    "body",
    ["not json", "{}", '{"messages": []}', '{"messages": [{"role": "system", "content": "x"}]}',
     '{"messages": [{"role": "user", "content": 5}]}', '{"messages": [{"role": "assistant", "content": "x"}]}'],
)  # fmt: skip
async def test_bad_requests_get_400(body):
    r = await AsyncClient().post("/api/chat", body, **POST)
    assert r.status_code == 400


async def test_oversized_body_rejected():
    big = json.dumps({"messages": [{"role": "user", "content": "x" * 70000}]})
    r = await AsyncClient().post("/api/chat", big, **POST)
    assert r.status_code in (400, 413)


async def test_only_post_allowed():
    assert (await AsyncClient().get("/api/chat")).status_code == 405


async def test_examples_endpoint():
    data = (await AsyncClient().get("/api/examples")).json()
    assert len(data["examples"]) >= 4


@pytest.mark.django_db
def test_system_prompt_mentions_scope_and_snapshot():
    p = build_system_prompt()
    assert "Baden-Württemberg" in p and "ALWAYS get numbers from tools" in p and "coordinates" in p.lower()


_ = FakeTools
