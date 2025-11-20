from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast

from fastapi import FastAPI
from slack_sdk.web.async_client import AsyncWebClient as SlackClient
from starlette.requests import Request
from temporalio.client import Client as TemporalClient

from pydantic_temporal_example.settings import get_settings
from pydantic_temporal_example.temporal_client import build_temporal_client


@asynccontextmanager
async def lifespan(_server: FastAPI) -> AsyncIterator[dict[str, Any]]:
    settings = get_settings()
    slack_client = SlackClient(token=settings.slack_bot_token, timeout=60)

    slack_bot_user_id: str = cast(str, (await slack_client.auth_test())["user_id"])  # pyright: ignore[reportUnknownMemberType]
    yield {"temporal_client": await build_temporal_client(), "slack_bot_user_id": slack_bot_user_id}


async def get_temporal_client(request: Request) -> TemporalClient:
    return request.state.temporal_client


async def get_slack_bot_user_id(request: Request) -> str:
    return request.state.slack_bot_user_id
