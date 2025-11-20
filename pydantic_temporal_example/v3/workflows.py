import asyncio
import json
from datetime import timedelta
from typing import Any

import logfire
from pydantic_ai.durable_exec.temporal import TemporalAgent
from temporalio import workflow
from temporalio.workflow import ActivityConfig

from pydantic_temporal_example.models import (
    MessageChannelsEvent,
    SlackConversationsRepliesRequest,
    SlackMessageID,
    SlackReply,
)
from pydantic_temporal_example.temporal.slack_activities import (
    slack_chat_post_message,
    slack_conversations_replies,
)
from pydantic_temporal_example.v3.agents import docs_answering_agent, triage_agent

temporal_triage_agent = TemporalAgent(
    triage_agent,
    name="triage_agent",
    model_activity_config=ActivityConfig(start_to_close_timeout=timedelta(seconds=300)),
)

temporal_docs_answering_agent = TemporalAgent(
    docs_answering_agent,
    name="docs_answering_agent",
    model_activity_config=ActivityConfig(start_to_close_timeout=timedelta(seconds=300)),
)


@workflow.defn
class SlackThreadWorkflow:
    def __init__(self) -> None:
        self._pending_events: asyncio.Queue[MessageChannelsEvent] = asyncio.Queue()
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
    async def submit_message_channels_event(self, event: MessageChannelsEvent):
        await self._pending_events.put(event)

    async def handle_event(self, event: MessageChannelsEvent):
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

        # Stringify the thread
        stringified_thread = json.dumps(
            self._thread_messages, indent=2
        )  # Note: it might be nice to better-format the thread messages

        # Check if this is a message we should respond to:
        triage_result = (await temporal_triage_agent.run(stringified_thread)).output
        if not triage_result.includes_relevant_question:
            logfire.info("no relevant question: {reasoning}", reasoning=triage_result.reasoning)
        else:
            # Generate a response
            result = (await temporal_docs_answering_agent.run(stringified_thread)).output
            content = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": result,
                    },
                },
            ]

            # Post the response
            await workflow.execute_activity(  # pyright: ignore[reportUnknownMemberType]
                slack_chat_post_message,
                SlackReply(
                    thread=SlackMessageID(channel=event.channel, ts=event.reply_thread_ts),
                    content=content,
                ),
                start_to_close_timeout=timedelta(seconds=10),
            )
