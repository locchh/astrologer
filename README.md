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

### Official Documentation
- **[Claude Agent SDK Python](https://platform.claude.com/docs/en/agent-sdk/python)** - Complete SDK reference
- **[Tool Input/Output Types](https://platform.claude.com/docs/en/agent-sdk/python#tool-input-output-types)** - Tool specification guide
- **[Agent Skills Best Practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)** - Skills development guidelines
- **[Skills Introduction](https://platform.claude.com/cookbook/skills-notebooks-01-skills-introduction)** - Interactive skills tutorial
- **[Cookbook](https://platform.claude.com/cookbook/)** - Code examples and patterns

### Code & Libraries
- **[claude-agent-sdk-python](https://github.com/anthropics/claude-agent-sdk-python)** - Official Python SDK
- **[FastMCP - A2A-brigde](https://fastmcp.me/MCP/Details/981/a2a-bridge)** - MCP framework with A2A bridge
- **[MCPMarket - A2A-brigde](https://mcpmarket.com/server/a2a-bridge)**
- **[regismesquita - MCP_A2A](https://github.com/regismesquita/MCP_A2A/tree/main)** - Agent-to-agent communication