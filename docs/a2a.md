# A2A Experiment — Claude Code Multi-Terminal Communication

The goal: run an A2A agent server in one terminal, then have Claude Code in another terminal communicate with it using the **a2a-bridge MCP**.

```ascii
Terminal A                          Terminal B
──────────────────────────          ──────────────────────────
python a2a_agent_v2.py              claude (Claude Code)
(AssistantAgent :8080)  ←── A2A ── (with a2a MCP bridge)
```

---

## Tools Used

| Tool | Purpose |
|------|---------|
| [GongRzhe/A2A-MCP-Server](https://github.com/GongRzhe/A2A-MCP-Server) | MCP bridge between Claude Code and A2A agents |
| [a2a SDK](https://github.com/google-a2a/a2a-python) | Google's Agent-to-Agent Python SDK |
| [claude-agent-sdk](https://github.com/anthropics/claude-agent-sdk-python) | Powering the assistant inside the agent |
| FastAPI + uvicorn | HTTP server for the A2A agent (v2) |

---

## Setup

### 1 — Add the MCP to Claude Code (project scope, once)

**Original (GongRzhe):**
```bash
claude mcp add --scope project a2a -- uvx a2a-mcp-server
```

**Our fixed fork (recommended):**
```bash
claude mcp add --scope project a2a -- uvx --from git+https://github.com/locchh/A2A-MCP-Server a2a-mcp-server
```

> The original has a bug where `send_message` returns empty — see [Problems & Fixes](#problems--fixes).

Verify:

```bash
claude mcp list
```

### 2 — Start the agent (Terminal A)

```bash
cd ~/Works/snx
python a2a_agent_v2.py
# INFO: Starting assistant agent (v2) on 0.0.0.0:8080
```

### 3 — Talk to it from Claude Code (Terminal B)

```bash
cd ~/Works/snx
claude
```

Ask Claude to register and communicate:

```
Register the A2A agent at http://localhost:8080, then ask it what files are in this project.
```

Claude will call these MCP tools in sequence:

1. `register_agent http://localhost:8080`
2. `send_message` → returns a `task_id`
3. `get_task_result task_id` → returns the agent's response

---

## Available MCP Tools

| Tool | What it does |
|------|-------------|
| `register_agent` | Register an A2A agent by URL |
| `list_agents` | List all registered agents |
| `unregister_agent` | Remove an agent |
| `send_message` | Send a prompt, returns `task_id` |
| `get_task_result` | Fetch the response by `task_id` |
| `send_message_stream` | Send with streaming (requires streaming=True agent) |
| `cancel_task` | Cancel a running task |

---

## Problems & Fixes

### Problem 1 — Protocol mismatch (a2a_agent.py v1)

`a2a_agent.py` used the new **A2A SDK 0.3.0** (`message/send`, `kind: "text"`).
The MCP bridge uses the **old protocol** (`tasks/send`, `type: "text"`).

**Fix:** Rewrote the agent as `a2a_agent_v2.py` — a plain FastAPI JSON-RPC server that speaks the old protocol the bridge expects, with no A2A SDK dependency.

### Problem 2 — `send_message` always returned empty (MCP bridge bug)

In `a2a_mcp_server.py`, the `send_message` tool accessed the wrong level of the response:

```python
# Bug: result is SendTaskResponse, not Task
if hasattr(result, "status") ...       # always False
for artifact in result.artifacts ...   # always empty

# Fix: Task is wrapped inside result.result
task = result.result
if hasattr(task, "status") ...
for artifact in task.artifacts ...
```

`SendTaskResponse` wraps the `Task` in its `.result` field, but the bridge was checking `.status` directly on the response object.

**Fix:** Forked the repo → [locchh/A2A-MCP-Server](https://github.com/locchh/A2A-MCP-Server) and patched `send_message` to extract data from `result.result` instead of `result`.

### Problem 3 — `get_task_result` returned empty (our server)

Even after fixing the bridge, `get_task_result` needed the task to be stored server-side. The original `a2a_agent_v2.py` returned an error for `tasks/get`.

**Fix:** Added a `task_store` dict in `a2a_agent_v2.py` — tasks are saved on `tasks/send` and returned on `tasks/get`.

---

## Multi-Agent Setup

Run multiple agents on different ports and have Claude coordinate:

```bash
# Terminal A
ASSISTANT_PORT=8080 python a2a_agent_v2.py

# Terminal B
ASSISTANT_PORT=8081 python a2a_agent_v2.py

# Terminal C — Claude Code
claude
# Register agents at :8080 and :8081, ask both the same question and compare.
```