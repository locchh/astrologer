import uuid
import asyncio
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
from .models import SessionStatus


class Session:
    def __init__(self):
        self.id = uuid.uuid4()
        self.status = SessionStatus.CREATED
        # ...