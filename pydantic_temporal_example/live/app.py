import logfire
import uvicorn
from fastapi import FastAPI

from pydantic_temporal_example.dependencies import lifespan
from pydantic_temporal_example.live.api import router
from pydantic_temporal_example.live.workflows import SlackThreadWorkflow
from pydantic_temporal_example.temporal_worker import temporal_worker

app = FastAPI(lifespan=lifespan)
app.include_router(router)

logfire.configure(service_name="app", scrubbing=False)
logfire.instrument_pydantic_ai()
logfire.instrument_httpx(capture_all=True)
logfire.instrument_fastapi(app)


async def main():
    async with temporal_worker([SlackThreadWorkflow], []):
        config = uvicorn.Config("pydantic_temporal_example.live.app:app", port=4000)
        server = uvicorn.Server(config)
        await server.serve()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
