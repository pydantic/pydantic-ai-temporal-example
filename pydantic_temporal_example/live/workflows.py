import asyncio
from typing import Any

from temporalio import workflow


@workflow.defn
class SlackThreadWorkflow:
    def __init__(self) -> None:
        self._pending_events: asyncio.Queue[Any] = asyncio.Queue()

    @workflow.run
    async def run(self) -> None:
        while True:
            await workflow.wait_condition(lambda: not self._pending_events.empty())
            while not self._pending_events.empty():
                event = self._pending_events.get_nowait()
                await self.handle_event(event)

    async def handle_event(self, event: Any) -> None:
        raise NotImplementedError
