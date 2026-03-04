"""
Local proxy between Claude Code and the custom provider.
- Strips unsupported anthropic-beta headers
- Converts streaming requests to non-streaming (provider doesn't support streaming)
- Fakes SSE stream back to Claude Code

Usage:
    python proxy.py

Then launch Claude Code with:
    set -a && source .env && set +a && claude --model Claude-Haiku-4.5
"""

import os
import sys
import json
import glob
from datetime import datetime
import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv

load_dotenv()

LOG_MAX_FILES = 5
LOG_DIR = "."


def _open_log_file():
    # Rotate: remove oldest logs if over limit
    logs = sorted(glob.glob(os.path.join(LOG_DIR, "proxy.*.log")))
    while len(logs) >= LOG_MAX_FILES:
        os.remove(logs.pop(0))
    filename = os.path.join(LOG_DIR, f"proxy.{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    return open(filename, "w", encoding="utf-8", buffering=1)


LOG_FILE = _open_log_file()


def log(level: str, msg: str):
    """
    Log a message to both console and file.
    Args:
        level (str): The log level (e.g., "INFO", "ERROR").
        msg (str): The log message.
    Returns:
        None
    """
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"{ts}  {level}  {msg}"
    print(line)
    LOG_FILE.write(line + "\n")


app = FastAPI()

TARGET_BASE_URL = os.getenv("MODEL_BASE_URL", "https://aiportalapi.stu-platform.live/jpe").rstrip("/")
TARGET_API_KEY = os.getenv("MODEL_API_KEY", "")

UNSUPPORTED_BETA_VALUES = {
    "prompt-caching-scope-2026-01-05",
    "interleaved-thinking-2025-05-14",
    "claude-code-20250219",
}

# Rewrite Anthropic model IDs → provider model name
DEFAULT_MODEL = "Claude-Sonnet-4.6"

MODEL_MAP = {
    # Long-form IDs (with date suffix)
    "claude-haiku-4-5-20251001": "Claude-Sonnet-4.6",
    "claude-sonnet-4-5-20250514": "Claude-Sonnet-4.6",
    "claude-sonnet-4-6-20250514": "Claude-Sonnet-4.6",
    "claude-opus-4-6-20250515": "Claude-Sonnet-4.6",
    # Short-form IDs (used by /model command)
    "claude-haiku-4-5": "Claude-Sonnet-4.6",
    "claude-sonnet-4-5": "Claude-Sonnet-4.6",
    "claude-sonnet-4-6": "Claude-Sonnet-4.6",
    "claude-opus-4-6": "Claude-Sonnet-4.6",
    # Backend model names (returned by /v1/models, used directly by Claude Code)
    "Claude-Haiku-4.5": "Claude-Sonnet-4.6",
}

client = httpx.AsyncClient(timeout=120)


def filter_beta_header(value: str) -> str | None:
    parts = [v.strip() for v in value.split(",") if v.strip() not in UNSUPPORTED_BETA_VALUES]
    return ",".join(parts) if parts else None


def build_headers(request: Request) -> dict:
    headers = {}
    for key, value in request.headers.items():
        low = key.lower()
        if low in ("host", "content-length", "transfer-encoding"):
            continue
        if low == "anthropic-beta":
            filtered = filter_beta_header(value)
            if filtered:
                headers[key] = filtered
        else:
            headers[key] = value
    return headers


def to_sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def fake_sse_stream(response_body: dict):
    msg_id = response_body.get("id", "msg_000")
    model = response_body.get("model", "")
    usage = response_body.get("usage", {})
    content = response_body.get("content", [])
    stop_reason = response_body.get("stop_reason", "end_turn")

    yield to_sse("message_start", {
        "type": "message_start",
        "message": {
            "id": msg_id, "type": "message", "role": "assistant",
            "content": [], "model": model,
            "stop_reason": None, "stop_sequence": None,
            "usage": {"input_tokens": usage.get("input_tokens", 0), "output_tokens": 0},
        },
    })
    for i, block in enumerate(content):
        if block.get("type") == "text":
            yield to_sse("content_block_start", {"type": "content_block_start", "index": i, "content_block": {"type": "text", "text": ""}})
            yield to_sse("content_block_delta", {"type": "content_block_delta", "index": i, "delta": {"type": "text_delta", "text": block.get("text", "")}})
            yield to_sse("content_block_stop", {"type": "content_block_stop", "index": i})

    yield to_sse("message_delta", {"type": "message_delta", "delta": {"stop_reason": stop_reason, "stop_sequence": None}, "usage": {"output_tokens": usage.get("output_tokens", 0)}})
    yield to_sse("message_stop", {"type": "message_stop"})


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
async def proxy(request: Request, path: str):
    url = f"{TARGET_BASE_URL}/{path}"
    query = "&".join(p for p in request.url.query.split("&") if not p.startswith("beta="))
    if query:
        url = f"{url}?{query}"

    headers = build_headers(request)
    body = await request.body()
    # Rewrite model name if needed
    try:
        body_json = json.loads(body)
        original_model = body_json.get("model", "")
        if original_model:
            mapped = MODEL_MAP.get(original_model, DEFAULT_MODEL)
            body_json["model"] = mapped
            if mapped != original_model:
                log("INFO", f"  model rewrite: {original_model} → {mapped}")
        body = json.dumps(body_json).encode()
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass

    is_stream = b'"stream":true' in body

    if is_stream:
        body = body.replace(b'"stream":true', b'"stream":false')

    log("INFO", f"→ {request.method} {url} {'[stream→sync]' if is_stream else '[sync]'}")
    log("INFO", f"  beta: {headers.get('anthropic-beta', '(none)')}")
    try:
        log("INFO", f"  body: {json.dumps(json.loads(body), indent=2)[:2000]}")
    except Exception:
        log("INFO", f"  body: {body[:500]}")

    r = await client.request(request.method, url, headers=headers, content=body)
    log("INFO", f"← {r.status_code} {r.reason_phrase}")

    if r.status_code != 200:
        log("ERROR", f"  error: {r.text[:500]}")
        return Response(content=r.content, status_code=r.status_code, media_type=r.headers.get("content-type"))

    if is_stream:
        response_body = r.json()
        log("INFO", f"  tokens: {response_body.get('usage', {})} | stop: {response_body.get('stop_reason')}")
        return StreamingResponse(fake_sse_stream(response_body), media_type="text/event-stream")

    return Response(content=r.content, status_code=r.status_code, media_type=r.headers.get("content-type"))


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8082))
    log("INFO", f"Proxy starting → {TARGET_BASE_URL}")
    log("INFO", f"Listening on 0.0.0.0:{port}")
    log("INFO", "Claude Code: set -a && source .env && set +a && claude --model <model_name>")
    uvicorn.run(app, host="0.0.0.0", port=port, log_config=None)
