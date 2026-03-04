#!/usr/bin/env python3
"""
Example demonstrating Skills usage with the Claude Agent SDK.

When using the Claude Agent SDK, Skills are:

    Defined as filesystem artifacts: Created as SKILL.md files in specific directories (.claude/skills/)
    Loaded from filesystem: Skills are loaded from configured filesystem locations. You must specify settingSources (TypeScript) or setting_sources (Python) to load Skills from the filesystem
    Automatically discovered: Once filesystem settings are loaded, Skill metadata is discovered at startup from user and project directories; full content loaded when triggered
    Model-invoked: Claude autonomously chooses when to use them based on context
    Enabled via allowed_tools: Add "Skill" to your allowed_tools to enable Skills

Unlike subagents (which can be defined programmatically), Skills must be created as filesystem artifacts. The SDK does not provide a programmatic API for registering Skills.

Default behavior: By default, the SDK does not load any filesystem settings. To use Skills, you must explicitly configure settingSources: ['user', 'project'] (TypeScript) or setting_sources=["user", "project"] (Python) in your options.
"""

from dotenv import load_dotenv

load_dotenv()

import json
import uuid
import asyncio
import textwrap
from pathlib import Path
from claude_agent_sdk import (
    query,
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


async def my_permission_callback(
    tool_name: str, input_data: dict, context: ToolPermissionContext
) -> PermissionResultAllow | PermissionResultDeny:
    """Control tool permissions based on tool type and input."""

    # Always allow read operations
    if tool_name in ["Read", "Glob", "Grep", "Skill"]:
        print(f"   ✅ Automatically allowing {tool_name} (read-only operation)")
        return PermissionResultAllow()

    if tool_name in ["Write", "Edit", "MultiEdit"]:
        file_path = input_data.get("file_path", "")
        if file_path.startswith("./tmp/session_") or file_path.startswith("./tmp/"):
            print(f"   ✅ Allowing write to session directory: {file_path}")
            return PermissionResultAllow()
        else:
            print(f"   ❌ Denying write to unauthorized directory: {file_path}")
            return PermissionResultDeny(
                message=f"Cannot write to unauthorized directory: {file_path}"
            )

    if tool_name == "Bash":
        command = input_data.get("command", "")
        dangerous_commands = ["rm -rf", "sudo", "chmod 777", "dd if=", "mkfs"]

        for dangerous in dangerous_commands:
            if dangerous in command:
                print(f"   ❌ Denying dangerous command: {command}")
                return PermissionResultDeny(
                    message=f"Dangerous command pattern detected: {dangerous}"
                )

        # Allow the command
        print(f"   ✅ Allowing bash command: {command}")
        return PermissionResultAllow()

    # For all other tools, ask the user
    print(f"   ❓ Unknown tool: {tool_name}")
    print(f"      Input: {json.dumps(input_data, indent=6)}")
    user_input = input("   Allow this tool? (y/N): ").strip().lower()

    if user_input in ("y", "yes"):
        return PermissionResultAllow()
    else:
        return PermissionResultDeny(message="User denied permission")


async def execute_skill_snapshot():

    # Generate a unique session ID for this run
    session_id = str(uuid.uuid4())[:8]
    print("=" * 50)
    print(f"Executing snapshot skill Session ID: {session_id}")
    print("=" * 50)

    options = ClaudeAgentOptions(
        cwd=str(Path(__file__).parent),  # Project with .claude/skills/
        setting_sources=["user", "project"],  # Load Skills from filesystem
        allowed_tools=["Skill", "Read", "Write", "Bash"],  # Enable Skill tool
        can_use_tool=my_permission_callback,
        permission_mode="default",  # Ensure callbacks are invoked
    )

    prompt = textwrap.dedent(f"""
            Show me the snapshot skill
            Then use it to generate a snapshot of the current project
            Save the snapshot to tmp/sessions/session_{session_id}/snapshot.md
            If the session directory does not exist, create it first
        """)

    async with ClaudeSDKClient(options) as client:
        await client.query(prompt)

        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                # Print Claude's text responses
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(f"\n💬 Claude: {block.text}")

                    elif isinstance(block, ToolUseBlock):
                        print(f"\n🔧 Tool: {block.name}")
                        print(f"   Input: {json.dumps(block.input, indent=2)}")

            elif isinstance(message, ResultMessage):
                print("\n✅ Task completed!")
                print(f"   Duration: {message.duration_ms}ms")


async def execute_skill_todo_scan():

    # Generate a unique session ID for this run
    session_id = str(uuid.uuid4())[:8]
    print("=" * 50)
    print(f"Executing todo-scan skill Session ID: {session_id}")
    print("=" * 50)

    options = ClaudeAgentOptions(
        cwd=str(Path(__file__).parent),
        setting_sources=["user", "project"],
        allowed_tools=["Skill", "Bash", "Write"],
        can_use_tool=my_permission_callback,
        permission_mode="default",
    )

    prompt = "Scan the codebase for TODO and FIXME comments and save the report. Save the report to ./todo-scan.txt"

    async with ClaudeSDKClient(options) as client:
        await client.query(prompt)

        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(f"\n💬 Claude: {block.text}")
                    elif isinstance(block, ToolUseBlock):
                        print(f"\n🔧 Tool: {block.name}")
                        print(f"   Input: {json.dumps(block.input, indent=2)}")

            elif isinstance(message, ResultMessage):
                print("\n✅ Task completed!")
                print(f"   Duration: {message.duration_ms}ms")


async def main():
    # Run both skills concurrently
    # Each skill will have its own session ID for isolation
    # This allows them to run independently without interfering with each other
    await asyncio.gather(
        execute_skill_snapshot(),
        execute_skill_todo_scan(),
    )


if __name__ == "__main__":
    asyncio.run(main())
