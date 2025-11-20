import logfire
from pydantic_ai.durable_exec.temporal import LogfirePlugin, PydanticAIPlugin
from temporalio.client import Client as TemporalClient

from pydantic_temporal_example.settings import get_settings


async def build_temporal_client() -> TemporalClient:
    settings = get_settings()
    temporal_host = settings.temporal_host or "localhost"
    temporal_port = settings.temporal_port

    def _setup_logfire() -> logfire.Logfire:
        instance = logfire.configure(scrubbing=False)
        logfire.instrument_pydantic_ai()
        logfire.instrument_httpx(capture_all=True)
        return instance

    return await TemporalClient.connect(
        f"{temporal_host}:{temporal_port}", plugins=[PydanticAIPlugin(), LogfirePlugin(_setup_logfire)]
    )
