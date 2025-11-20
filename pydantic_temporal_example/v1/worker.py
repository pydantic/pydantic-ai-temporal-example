from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

from pydantic_ai.durable_exec.temporal import AgentPlugin
from temporalio.worker import Worker

from pydantic_temporal_example.settings import get_settings
from pydantic_temporal_example.temporal.client import build_temporal_client
from pydantic_temporal_example.temporal.slack_activities import ALL_SLACK_ACTIVITIES
from pydantic_temporal_example.temporal.workflows import (
    SlackThreadWorkflow,
    temporal_dinner_research_agent,
    temporal_dispatch_agent,
    temporal_slack_bot_agent,
)


@asynccontextmanager
async def temporal_worker() -> AsyncIterator[Worker]:
    settings = get_settings()
    async with AsyncExitStack() as stack:
        if settings.temporal_host is None:
            from temporalio.testing import WorkflowEnvironment

            workflow_env = await WorkflowEnvironment.start_local(port=settings.temporal_port, ui=True)  # pyright: ignore[reportUnknownMemberType]
            await stack.enter_async_context(workflow_env)

        client = await build_temporal_client()
        yield await stack.enter_async_context(
            Worker(
                client,
                task_queue=settings.temporal_task_queue,
                workflows=[SlackThreadWorkflow],
                activities=ALL_SLACK_ACTIVITIES,
                plugins=[
                    AgentPlugin(temporal_dispatch_agent),
                    AgentPlugin(temporal_dinner_research_agent),
                    AgentPlugin(temporal_slack_bot_agent),
                ],
            )
        )
