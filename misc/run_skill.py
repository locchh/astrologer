"""
Run an interactive Claude skill session from the command line.

Usage:
    source .env
    python misc/run_skill.py "Tell my fortune, my birth date is 1990-05-15"

Claude will ask follow-up questions — just type your answers and press Enter.
Output files (if any) are written to ./tmp/sessions/<run_id>/.
"""

import asyncio
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    PermissionResultAllow,
    PermissionResultDeny,
    ResultMessage,
    TextBlock,
    ToolPermissionContext,
)

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SESSION_BASE = PROJECT_ROOT / "tmp" / "sessions"


async def permission_callback(
    tool_name: str, input_data: dict, context: ToolPermissionContext
) -> PermissionResultAllow | PermissionResultDeny:
    if tool_name in ("Read", "Glob", "Grep", "Skill"):
        return PermissionResultAllow()
    if tool_name in ("Write", "Edit", "MultiEdit"):
        file_path = input_data.get("file_path", "")
        if str(SESSION_BASE) in file_path or file_path.startswith("./tmp"):
            return PermissionResultAllow()
        return PermissionResultDeny(message=f"Write to {file_path!r} not allowed")
    if tool_name == "Bash":
        return PermissionResultAllow()
    return PermissionResultDeny(message=f"{tool_name} is not allowed")


def _text(message: AssistantMessage) -> str:
    return "".join(b.text for b in message.content if isinstance(b, TextBlock))


async def run(initial_prompt: str) -> None:
    run_id = str(uuid.uuid4())
    output_dir = SESSION_BASE / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    prompt = f"{initial_prompt}\n\nSave all output files to: {output_dir}"

    options = ClaudeAgentOptions(
        cwd=str(PROJECT_ROOT),
        setting_sources=["project"],
        allowed_tools=["Skill", "Read", "Write", "Bash"],
        can_use_tool=permission_callback,
        permission_mode="default",
    )

    print(f"[session] {run_id}")
    print(f"[output]  {output_dir}\n")

    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)

        while True:
            # Drain Claude's response for this turn
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    text = _text(message)
                    if text:
                        print(f"\nClaude: {text}")
                elif isinstance(message, ResultMessage):
                    pass  # session bookkeeping, ignore

            # Prompt for follow-up; empty line or EOF ends the session
            try:
                user_input = input("\nYou: ").strip()
            except EOFError:
                user_input = ""

            if not user_input:
                print("\n[done]")
                break

            await client.query(user_input)

    # Report any written files
    files = [f.name for f in output_dir.iterdir() if f.is_file()]
    if files:
        print(f"\n[files written to {output_dir}]")
        for f in sorted(files):
            print(f"  {f}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    asyncio.run(run(" ".join(sys.argv[1:])))
