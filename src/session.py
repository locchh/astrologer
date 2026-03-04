import time
import uuid
from pathlib import Path

import asyncio
from .models import SessionStatus

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    PermissionResultAllow,
    PermissionResultDeny,
    ResultMessage,
    ToolPermissionContext,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SESSION_BASE = PROJECT_ROOT / "tmp" / "sessions"


async def my_permission_callback(
    tool_name: str, input_data: dict, context: ToolPermissionContext
) -> PermissionResultAllow | PermissionResultDeny:
    if tool_name in ["Read", "Glob", "Grep", "Skill"]:
        return PermissionResultAllow()

    elif tool_name in ["Write", "Edit", "MultiEdit", "Bash"]:
        file_path = input_data.get("file_path", "")
        session_base = str(SESSION_BASE)
        if file_path.startswith("./tmp") or file_path.startswith(session_base):
            return PermissionResultAllow()
        # Bash commands (mkdir, etc.) always allowed
        if tool_name == "Bash":
            return PermissionResultAllow()
        return PermissionResultDeny(message=f"Write to {file_path} is not allowed")

    else:
        return PermissionResultDeny(message=f"{tool_name} is not allowed")


class AgentSession:
    def __init__(self):
        self.run_id: str = str(uuid.uuid4())
        self.claude_session_id: str | None = None
        self.status: SessionStatus = SessionStatus.CREATED
        self.output_dir: Path = SESSION_BASE / self.run_id
        self.output_dir.mkdir(parents=True, exist_ok=True)
        # REST POST /input pushes user messages here; _run() reads from it to continue the conversation
        self._input_queue: asyncio.Queue = asyncio.Queue()
        # _run() pushes all Claude messages here; SSE /stream drains it to the client
        self._message_queue: asyncio.Queue = asyncio.Queue()
        # the asyncio.Task running _run() in background; needed for cancel() and close()
        self._task: asyncio.Task | None = None
        self._timeout_task: asyncio.Task | None = None
        # stores the exception message if _run() fails; REST GET /sessions/{id} can return it
        self.error: str | None = None
        self.created_at: float = time.time()
        self.timeout_seconds: int = 20 * 60  # 20 minutes

    def start(self, prompt: str) -> None:
        """Spawn the background execution coroutine."""
        self._task = asyncio.create_task(self._run(prompt))
        self._timeout_task = asyncio.create_task(self._run_timeout())

    async def _run(self, prompt: str) -> None:
        try:
            options = ClaudeAgentOptions(
                cwd=str(PROJECT_ROOT),
                setting_sources=["project"],
                allowed_tools=["Skill", "Read", "Write", "Bash"],
                can_use_tool=my_permission_callback,
                permission_mode="default",
            )

            async with ClaudeSDKClient(options=options) as client:
                self.status = SessionStatus.RUNNING
                await client.query(prompt)

                while True:
                    # Receive Claude messages
                    async for message in client.receive_response():
                        # Update session ID
                        if isinstance(message, ResultMessage):
                            self.claude_session_id = message.session_id
                        # Push Claude messages to the queue
                        await self._message_queue.put(message)

                    # Turn ended → go IDLE, signal the SSE stream
                    self.status = SessionStatus.IDLE
                    await self._message_queue.put({"type": "idle", "files": self.output_files()})

                    # Wait for next user input or stop signal
                    user_input = await self._input_queue.get()
                    if user_input is None:
                        break

                    self.status = SessionStatus.RUNNING
                    await client.query(user_input)

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.error = str(exc)
            self.status = SessionStatus.FAILED
            await self._message_queue.put({"type": "error", "message": str(exc)})
        finally:
            self.status = SessionStatus.CLOSED

    async def _run_timeout(self) -> None:
        """Stop the session after timeout_seconds."""
        await asyncio.sleep(self.timeout_seconds)
        if self.status not in (SessionStatus.CLOSED, SessionStatus.FAILED):
            await self._message_queue.put({
                "type": "timeout",
                "message": f"Session stopped after {self.timeout_seconds // 60} minutes.",
            })
            await self._input_queue.put(None)

    async def send_input(self, message: str) -> None:
        """Inject a user follow-up message. Session must be IDLE."""
        await self._input_queue.put(message)

    async def cancel(self) -> None:
        """Send None sentinel to stop the loop gracefully."""
        await self._input_queue.put(None)

    async def close(self) -> None:
        """Hard stop — cancel the background task."""
        if self._timeout_task and not self._timeout_task.done():
            self._timeout_task.cancel()
        await self._input_queue.put(None)
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.status = SessionStatus.CLOSED

    def output_files(self) -> list[str]:
        """Return names of files in the output folder."""
        return [f.name for f in self.output_dir.iterdir() if f.is_file()]


class AgentSessionManager:
    def __init__(self):
        self._sessions: dict[str, AgentSession] = {}

    def create(self, prompt: str) -> AgentSession:
        """
        Create a new session.
        """
        session = AgentSession()
        self._sessions[session.run_id] = session
        full_prompt = f"{prompt}\n\nSave all output files to: {session.output_dir}"
        session.start(full_prompt)
        return session

    def get(self, run_id: str) -> AgentSession | None:
        """
        Get a session by ID.
        """
        return self._sessions.get(run_id)

    async def delete(self, run_id: str) -> None:
        """
        Delete a session by ID.
        """
        session = self._sessions.pop(run_id, None)
        # Close the session if it exists
        if session:
            await session.close()


manager = AgentSessionManager()
