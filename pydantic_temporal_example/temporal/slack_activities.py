# pyright: reportUnknownMemberType=false
from typing import Any, cast

import logfire
from httpx import AsyncClient
from slack_sdk.web.async_client import AsyncWebClient as SlackClient
from temporalio import activity

from pydantic_temporal_example.models import (
    SlackConversationsRepliesRequest,
    SlackInteractionResponse,
    SlackMessageID,
    SlackReaction,
    SlackReply,
)
from pydantic_temporal_example.settings import get_settings


@activity.defn
@logfire.instrument
async def slack_conversations_replies(request: SlackConversationsRepliesRequest) -> list[dict[str, Any]]:
    has_more = True
    next_cursor = None
    messages: list[dict[str, Any]] = []
    while has_more:
        response = await _get_slack_client().conversations_replies(
            channel=request.channel, ts=request.ts, oldest=request.oldest, next_cursor=next_cursor
        )
        response_messages = cast(list[dict[str, Any]], response["messages"])
        messages.extend(response_messages)
        has_more = response.get("has_more", False)
        if has_more:
            next_cursor = response.get("response_metadata", {}).get("next_cursor")

    return messages


@activity.defn
@logfire.instrument
async def slack_chat_post_message(reply: SlackReply) -> dict[str, Any]:
    response = await _get_slack_client().chat_postMessage(
        channel=reply.thread.channel,
        thread_ts=reply.thread.ts,
        text=reply.text,
        blocks=reply.blocks,
    )
    return cast(dict[str, Any], response.data)


@activity.defn
@logfire.instrument
async def slack_chat_delete(message: SlackMessageID) -> dict[str, Any]:
    response = await _get_slack_client().chat_delete(
        channel=message.channel,
        ts=message.ts,
    )
    return cast(dict[str, Any], response.data)


@activity.defn
@logfire.instrument
async def slack_reactions_add(reaction: SlackReaction) -> dict[str, Any]:
    response = await _get_slack_client().reactions_add(
        name=reaction.name,
        channel=reaction.message.channel,
        timestamp=reaction.message.ts,
    )
    return cast(dict[str, Any], response.data)


@activity.defn
@logfire.instrument
async def slack_reactions_remove(reaction: SlackReaction) -> dict[str, Any]:
    response = await _get_slack_client().reactions_remove(
        name=reaction.name,
        channel=reaction.message.channel,
        timestamp=reaction.message.ts,
    )
    return cast(dict[str, Any], response.data)


@activity.defn
@logfire.instrument
async def slack_get_permalink(message: SlackMessageID) -> dict[str, Any]:
    response = await _get_slack_client().chat_getPermalink(
        channel=message.channel,
        message_ts=message.ts,
    )
    return cast(dict[str, Any], response.data)


@activity.defn
async def slack_interaction_response(payload: SlackInteractionResponse):
    async with AsyncClient() as client:
        response = await client.post(payload.response_url, json={"replace_original": "true", "blocks": payload.blocks})
        if response.status_code >= 300:
            logfire.info(f"{response.content=} {response.status_code=}")
            response.raise_for_status()


ALL_SLACK_ACTIVITIES = [
    slack_conversations_replies,
    slack_chat_post_message,
    slack_chat_delete,
    slack_reactions_add,
    slack_reactions_remove,
    slack_get_permalink,
    slack_interaction_response,
]


def _get_slack_client() -> SlackClient:
    settings = get_settings()
    return SlackClient(token=settings.slack_bot_token, timeout=60)
