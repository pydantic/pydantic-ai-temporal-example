from dataclasses import dataclass

from pydantic import with_config
from pydantic_ai import Agent, WebSearchTool
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
    """,
)

server = MCPServerStreamableHTTP(url="https://mcp.deepwiki.com/mcp", timeout=30, id="deepwiki")

docs_answering_agent = Agent(
    "openai-responses:gpt-5-mini",
    toolsets=[server],
    builtin_tools=[WebSearchTool()],
    instructions="""\
    Use your tools to retrieve documentation and answer any questions related to the following repositories:
    * pydantic/pydantic
    * pydantic/pydantic-ai
    * pydantic/logfire
    * temporalio/sdk-python

    Notes:
    * You MUST NOT finish your response by prompting the user with follow-up questions — you will NOT be given any chance to follow up with the user. 
    * You MUST include any relevant links to the pydantic docs wherever possible. These links should be under https://ai.pydantic.dev/ or https://logfire.pydantic.dev/docs/.
    * Your answer will be sent as a slack message and therefore MUST be formatted as *Slack-compatible* "mrkdwn" text, with all the bizarre caveats of slack mrkdwn,
    including no using double-asterisks, no headers with more than 2 '#'s, no triple-backtick suffixes (i.e., just use '```', not '```python', etc.), and the slack format for links using angle brackets.
    * Your response MUST be less than 3001 characters
    """,
)
