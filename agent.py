from dotenv import load_dotenv
from pathlib import Path

load_dotenv()
from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock


class Assistant:
    """A simple assistant that can query the Claude Agent SDK."""
    
    def __init__(self) -> None:
        pass

    async def ask(self, prompt: str) -> str:
        """Ask the assistant a question and return the response."""
        options = ClaudeAgentOptions(
            allowed_tools=["Read", "Write", "Edit"],
            system_prompt="You are a helpful file assistant.",
            cwd=Path.cwd(),
        )

        response = ""

        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        response += block.text + "\n"
        
        return response.strip()

if __name__ == "__main__":
    import asyncio
    response = asyncio.run(Assistant().ask("What is the capital of France?"))
    print(response)
    print("Done!")
