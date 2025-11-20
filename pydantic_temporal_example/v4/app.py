import logfire
import uvicorn
from fastapi import FastAPI
from pydantic_ai.durable_exec.temporal import AgentPlugin

from pydantic_temporal_example.dependencies import lifespan
from pydantic_temporal_example.temporal_worker import temporal_worker
from pydantic_temporal_example.v4.api import router
from pydantic_temporal_example.v4.workflows import (
    SlackThreadWorkflow,
    temporal_docs_answering_agent,
    temporal_triage_agent,
)

app = FastAPI(lifespan=lifespan)
app.include_router(router)

logfire.configure(service_name="app", scrubbing=False)
logfire.instrument_pydantic_ai()
logfire.instrument_httpx(capture_all=True)
logfire.instrument_fastapi(app)


async def main():
    async with temporal_worker(
        [SlackThreadWorkflow], [AgentPlugin(temporal_docs_answering_agent), AgentPlugin(temporal_triage_agent)]
    ):
        config = uvicorn.Config("pydantic_temporal_example.v4.app:app", port=4000)
        server = uvicorn.Server(config)
        await server.serve()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
