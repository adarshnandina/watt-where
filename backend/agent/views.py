import json

from asgiref.sync import sync_to_async
from django.conf import settings
from django.http import HttpRequest, JsonResponse, StreamingHttpResponse
from django.views.decorators.http import require_GET, require_POST

from energy.tools import call_tool

from . import events as ev
from .loop import make_client, run_agent
from .prompts import EXAMPLE_QUESTIONS, build_system_prompt

MAX_MESSAGE_CHARS = 4000


class BadRequest(ValueError):
    pass


def parse_messages(request: HttpRequest) -> list[dict]:
    """Validate the request body; keep only the last CHAT_MAX_HISTORY messages."""
    if len(request.body) > settings.CHAT_MAX_BODY_BYTES:
        raise BadRequest("Request too large.")
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError as e:
        raise BadRequest("Body must be JSON.") from e
    msgs = body.get("messages") if isinstance(body, dict) else None
    if not isinstance(msgs, list) or not msgs:
        raise BadRequest("'messages' must be a non-empty list.")
    clean = []
    for m in msgs:
        if (
            not isinstance(m, dict)
            or m.get("role") not in ("user", "assistant")
            or not isinstance(m.get("content"), str)
        ):
            raise BadRequest("Each message needs role 'user'|'assistant' and string content.")
        text = m["content"].strip()
        if text:
            clean.append({"role": m["role"], "content": text[:MAX_MESSAGE_CHARS]})
    clean = clean[-settings.CHAT_MAX_HISTORY :]
    while clean and clean[0]["role"] != "user":  # the API needs the conversation to start with a user turn
        clean.pop(0)
    if not clean or clean[-1]["role"] != "user":
        raise BadRequest("The last message must be from the user.")
    return clean


async def _single_event(event: ev.Event):
    yield ev.message_start("msg_error")
    yield event
    yield ev.message_end({"input_tokens": 0, "output_tokens": 0}, "error")


@require_POST
async def chat(request: HttpRequest):
    """POST /api/chat: stream the agent's answer as Server-Sent Events."""
    try:
        messages = parse_messages(request)
    except BadRequest as e:
        return JsonResponse({"error": str(e)}, status=400)

    client = make_client()
    if client is None:
        events = _single_event(ev.error("The server has no ANTHROPIC_API_KEY configured.", False))
    else:
        system_prompt = await sync_to_async(build_system_prompt)()
        events = run_agent(messages, system_prompt, client)

    response = StreamingHttpResponse(ev.with_heartbeat(events), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"  # tell nginx-style proxies not to buffer the stream
    return response


@require_GET
async def examples(request: HttpRequest):
    return JsonResponse({"examples": EXAMPLE_QUESTIONS})


@require_GET
async def municipality_search(request: HttpRequest):
    """GET /api/municipalities/search?q=  (autocomplete)."""
    q = request.GET.get("q", "")
    result, _ = await sync_to_async(call_tool)("find_municipality", {"query": q[:100] or " ", "limit": 8})
    matches = result.llm_content.get("matches", [])
    return JsonResponse(
        {"results": [{"ags": m["ags"], "name": m["name"], "district": m["district_name"]} for m in matches]}
    )
