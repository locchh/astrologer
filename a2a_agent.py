import os

import uvicorn
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AStarletteApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from a2a.utils import new_agent_text_message
from dotenv import load_dotenv

load_dotenv()

from agent import Assistant


class AssistantExecutor(AgentExecutor):
    """A file assistant that can read, write, and edit files."""

    def __init__(self) -> None:
        self.agent = Assistant()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        prompt = context.get_user_input()
        response = await self.agent.ask(prompt)
        await event_queue.enqueue_event(new_agent_text_message(response))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        pass


def main() -> None:
    PORT = int(os.environ.get("ASSISTANT_PORT", 8080))
    HOST = os.environ.get("ASSISTANT_HOST", "0.0.0.0")

    print(f"Starting assistant agent on {HOST}:{PORT}")

    skill = AgentSkill(
        id="assistant",
        name="Assistant",
        description="A helpful assistant that can answer questions and perform tasks.",
        tags=["assistant", "help", "task"],
        examples=["What is the weather like today?", "Set a reminder for 3 PM"],
    )

    agent_card = AgentCard(
        name="Assistant",
        description="A helpful assistant that can answer questions and perform tasks.",
        url=f"http://{HOST}:{PORT}/",
        version="1.0.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=False),
        skills=[skill],
    )

    request_handler = DefaultRequestHandler(
        agent_executor=AssistantExecutor(),
        task_store=InMemoryTaskStore(),
    )

    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )

    uvicorn.run(server.build(), host=HOST, port=PORT)


if __name__ == "__main__":
    main()
