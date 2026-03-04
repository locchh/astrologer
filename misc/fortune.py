import os
import json
import uuid
import asyncio
import textwrap
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
os.environ.pop("CLAUDECODE", None)

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    PermissionResultAllow,
    PermissionResultDeny,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    AssistantMessage,
    ToolPermissionContext,
)

PROJECT_ROOT = Path(__file__).parent.parent


async def my_permission_callback(
    tool_name: str, input_data: dict, context: ToolPermissionContext  # noqa: ARG001
) -> PermissionResultAllow | PermissionResultDeny:
    if tool_name in ["Read", "Glob", "Grep", "Skill"]:
        return PermissionResultAllow()

    if tool_name in ["Write", "Edit", "MultiEdit", "Bash"]:
        return PermissionResultAllow()

    print(f"   ❓ Unknown tool: {tool_name}")
    user_input = input("   Allow this tool? (y/N): ").strip().lower()
    if user_input in ("y", "yes"):
        return PermissionResultAllow()
    return PermissionResultDeny(message="User denied permission")


async def do_fortune():
    session_id = str(uuid.uuid4())[:8]
    output_dir = f"tmp/sessions/session_{session_id}"

    print("=" * 50)
    print(f"🔮 Fortune Teller  |  Session: {session_id}")
    print("=" * 50)

    birth_date = input("Enter your birth date (e.g. March 5, 1990): ").strip()

    options = ClaudeAgentOptions(
        cwd=str(PROJECT_ROOT),
        setting_sources=["user", "project"],
        allowed_tools=["Skill", "Read", "Write", "Bash"],
        can_use_tool=my_permission_callback,
        permission_mode="default",
    )

    prompt = textwrap.dedent(f"""
        My birth date is {birth_date}.
        Please tell my fortune using the fortune skill.
        Save all output files to {output_dir}.
        Create the directory if it does not exist.
    """)

    async with ClaudeSDKClient(options) as client:
        await client.query(prompt)

        while True:
            last_text = ""

            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            print(f"\n💬 Claude: {block.text}")
                            last_text = block.text
                        elif isinstance(block, ToolUseBlock):
                            print(f"\n🔧 {block.name}: {json.dumps(block.input, indent=2)}")

                elif isinstance(message, ResultMessage):
                    # Check if output was generated — if so, we're done
                    if (PROJECT_ROOT / output_dir).exists():
                        print(f"\n✅ Done! ({message.duration_ms}ms)")
                        print(f"📁 Fortune saved to: {output_dir}/")
                        return

            # Output not generated yet — Claude must need more input
            if not (PROJECT_ROOT / output_dir).exists():
                answer = input("\n👤 You: ").strip()
                await client.query(answer)
            else:
                break


async def main():
    await do_fortune()


if __name__ == "__main__":
    asyncio.run(main())
