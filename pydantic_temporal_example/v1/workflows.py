import asyncio
import json
from datetime import timedelta
from typing import Any

from pydantic_ai.durable_exec.temporal import TemporalAgent
from temporalio import workflow

from pydantic_temporal_example.models import (
    AppMentionEvent,
    MessageChannelsEvent,
    SlackConversationsRepliesRequest,
    SlackMessageID,
    SlackReply,
)
from pydantic_temporal_example.temporal.slack_activities import (
    slack_chat_post_message,
    slack_conversations_replies,
)
from pydantic_temporal_example.v1.agent import docs_answering_agent

temporal_docs_answering_agent = TemporalAgent(
    docs_answering_agent,
    name="docs_answering_agent",
)


@workflow.defn
class SlackThreadWorkflow:
    def __init__(self) -> None:
        self._pending_events: asyncio.Queue[AppMentionEvent | MessageChannelsEvent | str] = asyncio.Queue()
        self._thread_messages: list[dict[str, Any]] = []

    @property
    def _most_recent_ts(self) -> str | None:
        if not self._thread_messages:
            return None
        # assume _thread_messages is always sorted by ts
        return self._thread_messages[-1]["ts"]

    @workflow.run
    async def run(self) -> None:
        while True:
            await workflow.wait_condition(lambda: not self._pending_events.empty())
            while not self._pending_events.empty():
                event = self._pending_events.get_nowait()
                await self.handle_event(event)

    @workflow.signal
    async def submit_app_mention_event(self, event: AppMentionEvent):
        await self._pending_events.put(event)

    async def handle_event(self, event: AppMentionEvent):
        # Load/update thread contents
        thread = SlackMessageID(channel=event.channel, ts=event.reply_thread_ts)
        request = SlackConversationsRepliesRequest(channel=thread.channel, ts=thread.ts, oldest=self._most_recent_ts)
        new_messages = await workflow.execute_activity(  # pyright: ignore[reportUnknownMemberType]
            slack_conversations_replies,
            request,
            start_to_close_timeout=timedelta(seconds=10),
        )
        for message in new_messages:
            self._thread_messages.append(message)
        self._thread_messages.sort(key=lambda m: m["ts"])

        # Generate a response
        stringified_thread = json.dumps(
            self._thread_messages, indent=2
        )  # Note: it might be nice to better-format the thread messages
        result = (await temporal_docs_answering_agent.run(stringified_thread)).output

        # Post the response
        await workflow.execute_activity(  # pyright: ignore[reportUnknownMemberType]
            slack_chat_post_message,
            SlackReply(
                thread=SlackMessageID(channel=event.channel, ts=event.reply_thread_ts),
                content=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": result,
                        },
                    },
                ],
            ),
            start_to_close_timeout=timedelta(seconds=10),
        )
