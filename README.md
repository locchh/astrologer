# Astrologer

## Setup

```bash
# Run the proxy
python proxy.py

# Run the backend
.venv/bin/python -m uvicorn astrologer.main:app --host ${BACKEND_HOST} --port ${BACKEND_PORT}

# Launch Claude Code
set -a && source .env && set +a && claude --model ${MODEL_NAME}
```

## References

- **[Claude Agent SDK Python - GitHub](https://github.com/anthropics/claude-agent-sdk-python)** - Official SDK repository
- **[Claude Agent SDK Python - Documentation](https://platform.claude.com/docs/en/agent-sdk/python)** - Complete SDK reference
- **[Tool Input/Output Types](https://platform.claude.com/docs/en/agent-sdk/python#tool-input-output-types)** - Tool specification guide
- **[Agent Skills Best Practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)** - Skills development guidelines
- **[Skills Introduction](https://platform.claude.com/cookbook/skills-notebooks-01-skills-introduction)** - Interactive skills tutorial
- **[Cookbook](https://platform.claude.com/cookbook/)** - Code examples and patterns