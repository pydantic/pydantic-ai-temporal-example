from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any

from temporalio.worker import Worker, Plugin

from pydantic_temporal_example.settings import get_settings
from pydantic_temporal_example.temporal.client import build_temporal_client
from pydantic_temporal_example.temporal.slack_activities import ALL_SLACK_ACTIVITIES


@asynccontextmanager
async def temporal_worker(workflows: list[type[Any]], plugins: list[Plugin]) -> AsyncIterator[Worker]:
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
                workflows=workflows,
                activities=ALL_SLACK_ACTIVITIES,
                plugins=plugins,
            )
        )
