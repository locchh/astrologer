import asyncio
import pytest
from dotenv import load_dotenv
load_dotenv()

from claude_agent_sdk import ClaudeSDKClient


@pytest.mark.anyio
async def test_llm():
    async with ClaudeSDKClient() as client:
        await client.query("Hello Claude")
        async for message in client.receive_response():
            print(message)

if __name__ == "__main__":
    asyncio.run(test_llm())