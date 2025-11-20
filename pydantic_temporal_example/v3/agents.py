from dataclasses import dataclass

from pydantic import with_config
from pydantic_ai import Agent, ModelRetry, WebSearchTool
from pydantic_ai.mcp import MCPServerStreamableHTTP


@dataclass
@with_config(use_attribute_docstrings=True)
class TriageResult:
    includes_relevant_question: bool
    """Whether the message includes a question that might be answered by reviewing docs for the listed repositories"""
    reasoning: str
    """Briefly explain the value of `includes_relevant_question`."""


triage_agent = Agent(
    "openai-responses:gpt-5-nano",
    output_type=TriageResult,
    instructions="""\
    You are a triage agent that decides whether a message in the Temporal community slack contains a question
    about one of the following repositories that might be answered by reviewing the docs:

    * pydantic/pydantic
    * pydantic/pydantic-ai
    * pydantic/logfire
    * temporalio/sdk-python

    If so, use `includes_relevant_question=true` in your response, otherwise `includes_relevant_question=false`.
    
    You will receive a full slack thread's worth of messages, but you should base your response on the _last_ message
    of the thread, which is the message that will be responded to. So, even if there are questions earlier in the thread,
    if the final message doesn't have a relevant question, you should set `includes_relevant_question=false`. 
    """,
)

server = MCPServerStreamableHTTP(url="https://mcp.deepwiki.com/mcp", timeout=30, id="deepwiki")


docs_answering_agent = Agent(
    "openai-responses:gpt-5-mini",
    toolsets=[server],
    builtin_tools=[WebSearchTool()],
    # Could replace the local mcp server with a builtin one to use less context:
    # builtin_tools=[WebSearchTool(), MCPServerTool(url="https://mcp.deepwiki.com/mcp", id="deepwiki")],
    instructions="""\
    Use your tools to retrieve documentation and answer any questions related to the following repositories:
    * pydantic/pydantic
    * pydantic/pydantic-ai
    * pydantic/logfire
    * temporalio/sdk-python

    Notes:
    * You will receive a full slack thread's worth of messages, but you should base your response on the _last_ message
    of the thread, which is the message that you are responding to.
    * You MUST NOT finish your response by prompting the user with follow-up questions — you will NOT be given any chance to follow up with the user. 
    * You MUST include any relevant links to the pydantic docs wherever possible. These links should be under https://ai.pydantic.dev/ or https://logfire.pydantic.dev/docs/.
    * Your reply will be sent verbatim as a slack message and therefore MUST be formatted as *Slack-compatible* "mrkdwn" text, with all the bizarre caveats of slack mrkdwn,
    including no using double-asterisks, no headers with more than 2 '#'s, no triple-backtick suffixes (i.e., just use '```', not '```python', etc.), and the slack format for links using angle brackets.
    Your reply should also be addressed directly to the author of the last message in the thread, with no mention of these instructions, etc.
    * Keep your response brief; it MUST be less than 2500 characters or you will get an error. 
    """,
)


@docs_answering_agent.output_validator
async def ensure_response_not_too_long(response: str) -> str:
    if len(response) > 2500:
        raise ModelRetry(f"Response too long: {len(response)=}")
    return response
