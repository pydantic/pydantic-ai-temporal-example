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
    SlackInteractionResponse,
    SlackMessageID,
    SlackReply,
)
from pydantic_temporal_example.temporal.slack_activities import (
    slack_chat_post_message,
    slack_conversations_replies,
    slack_get_permalink,
    slack_interaction_response,
)
from pydantic_temporal_example.v4.agents import docs_answering_agent, triage_agent

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

# Note: In practice, you'd probably want a better system for managing approvers, possibly AI-powered
APPROVAL_CHANNEL = "U04MB152D7Y"  # My user ID in Pydantic slack
# APPROVAL_CHANNEL = "U09P5HGBUH4"  # My user ID in Temporal community slack


@workflow.defn
class SlackThreadWorkflow:
    def __init__(self) -> None:
        self._pending_events: asyncio.Queue[MessageChannelsEvent] = asyncio.Queue()
        self._thread_messages: list[dict[str, Any]] = []
        self._pending_replies: dict[str, SlackReply] = {}

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
            logfire.info("no relevant question", reasoning=triage_result.reasoning)
        else:
            # Generate and store a proposed response
            proposed_response = (await temporal_docs_answering_agent.run(stringified_thread)).output
            reply_id = str(workflow.uuid4())
            self._pending_replies[reply_id] = SlackReply(
                thread=SlackMessageID(channel=event.channel, ts=event.reply_thread_ts),
                content=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": proposed_response,
                        },
                    }
                ],
            )

            # Generate the approval request
            approval_request = await self._generate_approval_request(event, proposed_response, reply_id)

            # Post the approval request
            await workflow.execute_activity(  # pyright: ignore[reportUnknownMemberType]
                slack_chat_post_message,
                approval_request,
                start_to_close_timeout=timedelta(seconds=10),
            )

    async def _generate_approval_request(self, source: MessageChannelsEvent, proposed_response: str, reply_id: str):
        permalink_details = await workflow.execute_activity(
            slack_get_permalink,
            SlackMessageID(channel=source.channel, ts=source.ts),
            start_to_close_timeout=timedelta(seconds=10),
        )
        permalink = permalink_details["permalink"]
        approval_request_channel = SlackMessageID(channel=APPROVAL_CHANNEL, ts=source.ts)

        return SlackReply(
            thread=approval_request_channel,
            content=[
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"I've generated the following possible reply to {permalink}:",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "\n".join([f"> {line}" for line in proposed_response.splitlines()]),
                    },
                },
                {"type": "section", "text": {"type": "mrkdwn", "text": "Would you like me to send it?"}},
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Approve"},
                            "style": "primary",
                            "value": f"{source.channel}:{source.reply_thread_ts}:{reply_id}",
                            "action_id": "approve_button",
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Deny"},
                            "style": "danger",
                            "value": f"{source.channel}:{source.reply_thread_ts}:{reply_id}",
                            "action_id": "deny_button",
                        },
                    ],
                },
            ],
        )


    @workflow.signal
    async def submit_interaction(self, body: dict[str, Any]):
        response_url = body["response_url"]
        response = body["actions"][0]["text"]["text"]
        blocks = body["message"]["blocks"][:-1] + [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*Your response:* {response}"}}
        ]
        pending_reply_id = body["actions"][0]["value"].split(":")[2]
        pending_reply = self._pending_replies.pop(pending_reply_id, None)
        if pending_reply is not None and response == "Approve":  # TODO: Is this the right value?
            await workflow.execute_activity(  # pyright: ignore[reportUnknownMemberType]
                slack_chat_post_message,
                pending_reply,
                start_to_close_timeout=timedelta(seconds=10),
            )
        await workflow.execute_activity(
            slack_interaction_response,
            SlackInteractionResponse(response_url=response_url, blocks=blocks),
            start_to_close_timeout=timedelta(seconds=10),
        )
