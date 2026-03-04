import asyncio
import os

import httpx
from a2a.client import Client, ClientConfig, ClientFactory, create_text_message_object
from a2a.types import AgentCard, Artifact, Message, Task
from a2a.utils.message import get_message_text
from dotenv import load_dotenv

load_dotenv()

HOST = os.environ.get("ASSISTANT_HOST", "localhost")
PORT = int(os.environ.get("ASSISTANT_PORT", 8080))

prompt = "Read the README.md file and summarize it"


def display_agent_card(agent_card: AgentCard) -> None:
    print(f"\n=== Agent Card ===")
    print(f"Name:        {agent_card.name}")
    print(f"Description: {agent_card.description}")
    print(f"Version:     {agent_card.version}")
    print(f"URL:         {agent_card.url}")
    if agent_card.skills:
        print("Skills:")
        for skill in agent_card.skills:
            examples = ", ".join(skill.examples) if skill.examples else "N/A"
            print(f"  - {skill.name}: {skill.description} (examples: {examples})")
    print("=" * 18)


async def main() -> None:
    async with httpx.AsyncClient(timeout=100.0) as httpx_client:
        # Step 1: Connect to the agent
        client: Client = await ClientFactory.connect(
            f"http://{HOST}:{PORT}",
            client_config=ClientConfig(httpx_client=httpx_client),
        )

        # Step 2: Fetch and display the agent card
        agent_card = await client.get_card()
        display_agent_card(agent_card)

        # Step 3: Send the prompt
        message = create_text_message_object(content=prompt)
        print(f"\nSending: {prompt!r}\n")

        # Step 4: Process responses
        text_content = ""
        async for response in client.send_message(message):
            if isinstance(response, Message):
                print(f"Message ID: {response.message_id}")
                text_content = get_message_text(response)
            elif isinstance(response, tuple):
                task: Task = response[0]
                print(f"Task ID: {task.id}")
                if task.artifacts:
                    artifact: Artifact = task.artifacts[0]
                    print(f"Artifact ID: {artifact.artifact_id}")
                    text_content = get_message_text(artifact)

        print("\n=== Response ===")
        print(text_content if text_content else "No response received.")


if __name__ == "__main__":
    asyncio.run(main())
