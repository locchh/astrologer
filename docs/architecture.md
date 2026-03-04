# Claude Agent SDK Python — Architecture

## Overview

The Claude Agent SDK is a Python library (v0.1.45) that provides async interfaces for programmatic interaction with the Claude Code CLI. It supports one-shot queries, bidirectional streaming conversations, custom tools via MCP servers, and advanced lifecycle hooks.

**Requirements:** Python 3.10+, anyio>=4.0.0, mcp>=0.1.0

---

## Layered Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Public API                        │
│         query()            ClaudeSDKClient           │
└────────────────┬──────────────────┬─────────────────┘
                 │                  │
                 ▼                  ▼
┌─────────────────────────────────────────────────────┐
│               InternalClient                         │
│     Coordinates transport, Query, and sessions       │
└──────────────────────────┬──────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────┐
│                     Query                            │
│   Control protocol: hooks, permissions, MCP mgmt    │
└──────────────────────────┬──────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────┐
│           SubprocessCLITransport                     │
│   anyio subprocess, stream-JSON over stdin/stdout   │
└──────────────────────────┬──────────────────────────┘
                           │ stdin/stdout
                           ▼
                  Claude Code CLI process
```

---

## File Structure

```
src/claude_agent_sdk/
├── __init__.py                    # Public exports (60+ types, functions, classes)
├── query.py                       # query() one-shot function
├── client.py                      # ClaudeSDKClient interactive sessions
├── types.py                       # All type definitions (~1100 lines)
├── _errors.py                     # Error hierarchy
└── _internal/
    ├── client.py                  # InternalClient coordination
    ├── query.py                   # Control protocol handler
    ├── sessions.py                # list_sessions(), get_session_messages()
    ├── message_parser.py          # JSON → typed Message objects
    └── transport/
        └── subprocess_cli.py      # CLI subprocess management
```

---

## Public API

### `query()` — One-Shot Queries

```python
async def query(
    *,
    prompt: str | AsyncIterable[dict],
    options: ClaudeAgentOptions | None = None,
    transport: Transport | None = None,
) -> AsyncIterator[Message]
```

Stateless fire-and-forget. Sends prompt, streams back messages, no conversation state persisted.

### `ClaudeSDKClient` — Interactive Sessions

Stateful bidirectional connection for multi-turn conversations.

| Method | Description |
|--------|-------------|
| `await client.connect(prompt)` | Establish connection (also async context manager) |
| `await client.query(prompt)` | Send a new message |
| `async for msg in client.receive_response()` | Stream complete response |
| `async for msg in client.receive_messages()` | Stream raw messages |
| `await client.interrupt()` | Send interrupt signal |
| `await client.set_permission_mode(mode)` | Change permission mode mid-session |
| `await client.get_mcp_status()` | Query MCP server status |
| `await client.reconnect_mcp_server(name)` | Reconnect a failed MCP server |
| `await client.toggle_mcp_server(name, enabled)` | Enable/disable MCP server |
| `await client.stop_task(task_id)` | Stop a running task |
| `await client.rewind_files(user_message_id)` | Rewind file state to checkpoint |

---

## Type System

### Message Types

```
Message (union)
├── UserMessage          — user prompt, tool results
├── AssistantMessage     — model response with content blocks
├── SystemMessage        — system/metadata events
│   ├── TaskStartedMessage
│   ├── TaskProgressMessage
│   └── TaskNotificationMessage
└── ResultMessage        — end-of-response marker (cost, usage, session_id)
```

### Content Blocks

```
ContentBlock (union)
├── TextBlock            — text: str
├── ThinkingBlock        — thinking: str, signature: str
├── ToolUseBlock         — id, name, input: dict
└── ToolResultBlock      — tool_use_id, content, is_error
```

### `ClaudeAgentOptions` — Main Configuration

| Category | Key Fields |
|----------|-----------|
| Model | `model`, `fallback_model`, `thinking`, `effort` |
| Tools | `tools`, `allowed_tools`, `disallowed_tools`, `can_use_tool` |
| Permissions | `permission_mode`, `permission_prompt_tool_name` |
| MCP Servers | `mcp_servers` (stdio / SSE / HTTP / SDK in-process) |
| Conversation | `system_prompt`, `max_turns`, `max_budget_usd`, `continue_conversation`, `resume` |
| Environment | `cwd`, `cli_path`, `env`, `add_dirs`, `sandbox` |
| Advanced | `agents`, `hooks`, `betas`, `output_format`, `enable_file_checkpointing` |
| I/O | `stderr`, `max_buffer_size`, `include_partial_messages` |

---

## Transport Layer

**Abstract base:** `Transport`

```python
class Transport(ABC):
    async def connect() -> None
    async def write(data: str) -> None
    def read_messages() -> AsyncIterator[dict]
    async def close() -> None
    def is_ready() -> bool
    async def end_input() -> None
```

**Default implementation:** `SubprocessCLITransport`

- Locates CLI: bundled → system-wide → known paths (min version 2.0.0)
- Translates `ClaudeAgentOptions` into CLI arguments
- Manages anyio subprocess with task groups
- Communicates via stream-JSON newline-delimited protocol
- Handles stderr redirection for debug logging

---

## Control Protocol (Internal)

The `Query` class implements an SDK-side control protocol layered on top of the raw transport:

**Initialization sequence:**
1. Connect transport, start anyio task group
2. Start message-reading task
3. Send `SDKControlInitializeRequest` (hooks, agents, SDK MCP servers)
4. Wait for initialization handshake

**Request types sent to CLI:**

| Request | Purpose |
|---------|---------|
| `SDKControlInitializeRequest` | Send hooks, agent definitions |
| `SDKControlPermissionRequest` | Resolve tool permission decisions |
| `SDKControlInterruptRequest` | Send interrupt signal |
| `SDKControlSetPermissionModeRequest` | Change permission mode |
| `SDKControlMcpToggleRequest` | Enable/disable MCP server |
| `SDKControlMcpReconnectRequest` | Reconnect failed MCP server |
| `SDKControlRewindFilesRequest` | Rewind file state to checkpoint |
| `SDKHookCallbackRequest` | Return hook execution results |

---

## In-Process MCP Servers

SDK MCP servers run in-process (no subprocess overhead) and have direct access to application state.

```python
@tool(name, description, input_schema)
async def my_tool(args: dict) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": "result"}]}

server = create_sdk_mcp_server(name="my-server", version="1.0.0", tools=[my_tool])
options = ClaudeAgentOptions(mcp_servers={"server": server})
```

**External MCP server types:** stdio (command), SSE (URL), HTTP (URL)

---

## Hooks System

Lifecycle hooks intercept and control SDK events.

**Events:** `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `UserPromptSubmit`, `Stop`, `SubagentStop`, `PreCompact`, `Notification`, `SubagentStart`, `PermissionRequest`

```python
async def my_hook(
    input: HookInput,
    tool_use_id: str | None,
    context: HookContext,
) -> HookJSONOutput:
    # Return control decisions
    pass

options = ClaudeAgentOptions(
    hooks={"PreToolUse": [HookMatcher(matcher="Bash", hooks=[my_hook])]}
)
```

**Hook output controls:** `continue_`, `decision` ("block"), `suppressOutput`, `hookSpecificOutput`

---

## Permission System

**Permission modes:**

| Mode | Behavior |
|------|----------|
| `"default"` | CLI prompts for dangerous tools |
| `"acceptEdits"` | Auto-accept file edits |
| `"plan"` | Review tool use before execution |
| `"bypassPermissions"` | Allow all tools |

**Custom permission callback:**

```python
async def can_use_tool(
    tool_name: str,
    input_dict: dict[str, Any],
    context: ToolPermissionContext,
) -> PermissionResult:
    # Return PermissionResultAllow or PermissionResultDeny
    pass
```

---

## Session Management

```python
# List all sessions
sessions: list[SDKSessionInfo] = await list_sessions(cwd="/my/project")
# SDKSessionInfo fields: session_id, summary, last_modified, file_size,
#                        custom_title, first_prompt, git_branch, cwd

# Retrieve message history
messages: list[SessionMessage] = await get_session_messages(session_id, cwd)
# SessionMessage fields: type, uuid, session_id, message, parent_tool_use_id
```

---

## Error Hierarchy

```
ClaudeSDKError
├── CLIConnectionError
│   └── CLINotFoundError
├── ProcessError          — exit codes, stderr
├── CLIJSONDecodeError    — malformed JSON from CLI
└── MessageParseError     — unknown message type
```

---

## Usage Patterns

### Minimal

```python
async for msg in query(prompt="Hello"):
    print(msg)
```

### With Options

```python
options = ClaudeAgentOptions(
    system_prompt="You are an expert Python developer",
    allowed_tools=["Read", "Write", "Bash"],
    permission_mode="acceptEdits",
    max_turns=5,
    cwd="/my/project",
)
async for msg in query(prompt="Refactor this code", options=options):
    print(msg)
```

### Interactive Session

```python
async with ClaudeSDKClient(options) as client:
    await client.query("Start an analysis")
    async for msg in client.receive_response():
        if isinstance(msg, AssistantMessage):
            print(msg)
        elif isinstance(msg, ResultMessage):
            print(f"Cost: ${msg.total_cost_usd}")

    await client.query("Now implement the fix")
    async for msg in client.receive_response():
        print(msg)
```
