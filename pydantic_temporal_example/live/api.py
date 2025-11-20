# pyright: reportUnknownMemberType=false
from typing import Any, assert_never

import logfire
from fastapi import APIRouter, Depends
from starlette.responses import JSONResponse, Response

from pydantic_temporal_example.dependencies import TemporalClient, get_temporal_client
from pydantic_temporal_example.models import SlackEventsAPIBody, URLVerificationEvent
from pydantic_temporal_example.slack import get_verified_slack_events_body

router = APIRouter()


@router.post("/slack-events")
async def handle_event(
    *,
    temporal_client: TemporalClient = Depends(get_temporal_client),
    body: SlackEventsAPIBody | URLVerificationEvent | dict[str, Any] = Depends(get_verified_slack_events_body),
) -> Response:
    """This should be used as the endpoint for the Slack Events API for your bot."""
    if isinstance(body, dict):
        logfire.warn("Unhandled Slack event", body=body)
    elif isinstance(body, URLVerificationEvent):
        return await handle_url_verification_event(body)
    elif isinstance(body, SlackEventsAPIBody):
        pass
    else:
        assert_never(body)

    return Response(status_code=204)


async def handle_url_verification_event(event: URLVerificationEvent) -> JSONResponse:
    return JSONResponse(content={"challenge": event.challenge})
