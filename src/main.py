"""
source .env
.venv/bin/python -m uvicorn src.main:app --host ${BACKEND_HOST} --port ${BACKEND_PORT}
"""

import os
import json
import asyncio

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock

from .session import manager
from .models import SessionStatus

os.environ.pop("CLAUDECODE", None)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request schemas ───────────────────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    prompt: str

class InputRequest(BaseModel):
    message: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

# Create a new session
@app.post("/sessions")
async def create_session(body: CreateSessionRequest):
    session = manager.create(body.prompt)
    return {"run_id": session.run_id, "status": session.status}


# Get session status
@app.get("/sessions/{run_id}")
async def get_session(run_id: str):
    session = manager.get(run_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "run_id": session.run_id,
        "status": session.status,
        "claude_session_id": session.claude_session_id,
        "output_files": session.output_files(),
        "error": session.error,
        "created_at": session.created_at,
        "timeout_seconds": session.timeout_seconds,
    }


# Stream session messages
@app.get("/sessions/{run_id}/stream")
async def stream_session(run_id: str):
    session = manager.get(run_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    async def event_generator():
        while True:
            try:
                message = await asyncio.wait_for(session._message_queue.get(), timeout=30)
                yield f"data: {json.dumps(_serialize(message))}\n\n"

                # Stop streaming when session is closed
                if session.status == SessionStatus.CLOSED:
                    break
            except asyncio.TimeoutError:
                yield "data: {\"type\": \"ping\"}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# Send user input
@app.post("/sessions/{run_id}/input")
async def send_input(run_id: str, body: InputRequest):
    session = manager.get(run_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != SessionStatus.IDLE:
        raise HTTPException(status_code=409, detail=f"Session is {session.status}, not idle")
    await session.send_input(body.message)
    return {"ok": True}


# Cancel session
@app.post("/sessions/{run_id}/cancel")
async def cancel_session(run_id: str):
    session = manager.get(run_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    await session.cancel()
    return {"ok": True}


# Delete session
@app.delete("/sessions/{run_id}")
async def delete_session(run_id: str):
    session = manager.get(run_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    await manager.delete(run_id)
    return {"ok": True}


# Get file
@app.get("/sessions/{run_id}/files/{filename}")
async def get_file(run_id: str, filename: str):
    session = manager.get(run_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    file_path = session.output_dir / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return StreamingResponse(open(file_path, "rb"), media_type="text/plain")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _serialize(message) -> dict:
    """Convert SDK messages and internal events to JSON-serializable dicts."""
    if isinstance(message, dict):
        return message
    if isinstance(message, AssistantMessage):
        text = "".join(b.text for b in message.content if isinstance(b, TextBlock))
        return {"type": "assistant", "text": text}
    if isinstance(message, ResultMessage):
        return {"type": "result", "session_id": message.session_id}
    return {"type": type(message).__name__, "data": str(message)}
