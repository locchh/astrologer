## Setup

```bash
# Run the proxy
python proxy.py

# Launch Claude Code
set -a && source .env && set +a && claude --model ${MODEL_NAME}
```

## TODO

💡 Use proxy for observability and debugging

💡 A2A + claude code

## References

https://platform.claude.com/docs/en/agent-sdk/python#tool-input-output-types

https://platform.claude.com/docs/en/agent-sdk/python

https://github.com/anthropics/claude-agent-sdk-python

https://fastmcp.me/MCP/Details/981/a2a-bridge

https://github.com/regismesquita/MCP_A2A/tree/main