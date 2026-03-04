import anyio
from dotenv import load_dotenv
load_dotenv()

from claude_agent_sdk import query

async def main():
    async for message in query(prompt="What is 2 + 2?"):
        print(message)

anyio.run(main)