from typing import Annotated, Any, Literal

from pydantic import BaseModel, Discriminator, TypeAdapter
from typing_extensions import TypeAlias


class MessageChannelsEvent(BaseModel):
    type: Literal["message"]
    user: str
    text: str
    ts: str
    channel: str
    event_ts: str
    channel_type: str
    thread_ts: str | None = None

    @property
    def reply_thread_ts(self) -> str:
        return self.thread_ts or self.ts


class AppMentionEvent(BaseModel):
    type: Literal["app_mention"]
    user: str
    text: str
    ts: str
    channel: str
    event_ts: str
    thread_ts: str | None = None

    @property
    def reply_thread_ts(self) -> str:
        return self.thread_ts or self.ts


class URLVerificationEvent(BaseModel):
    type: Literal["url_verification"]
    token: str
    challenge: str


SlackEvent: TypeAlias = Annotated[
    AppMentionEvent | MessageChannelsEvent, Discriminator("type")
]  # extendable for other event types; see https://docs.slack.dev/reference/events/


class SlackEventsAPIBody(BaseModel):
    token: str
    team_id: str  # | None = None
    api_app_id: str  # | None = None
    event: SlackEvent
    type: Literal["event_callback"]
    event_id: str
    event_time: int
    authed_users: list[str] | None = None


SlackEventsAPIBodyAdapter: TypeAdapter[SlackEventsAPIBody | URLVerificationEvent | dict[str, Any]] = TypeAdapter(
    Annotated[SlackEventsAPIBody | URLVerificationEvent, Discriminator("type")] | dict[str, Any]
)


class SlackMessageID(BaseModel):
    channel: str
    ts: str | None


class SlackReply(BaseModel):
    thread: SlackMessageID
    content: str | list[dict[str, Any]]

    @property
    def text(self) -> str | None:
        return self.content if isinstance(self.content, str) else None

    @property
    def blocks(self) -> list[dict[str, Any]] | None:
        return self.content if not isinstance(self.content, str) else None


class SlackReaction(BaseModel):
    message: SlackMessageID
    name: str


class SlackConversationsRepliesRequest(BaseModel):
    # See https://docs.slack.dev/reference/methods/conversations.replies/

    channel: str
    ts: str
    oldest: str | None  # only include messages after this unix timestamp


class SlackInteractionResponse(BaseModel):
    response_url: str
    blocks: list[dict[str, Any]]
