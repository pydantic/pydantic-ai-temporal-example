from dataclasses import dataclass

import logfire
from pydantic import with_config
from pydantic_ai import MCPServerTool, WebSearchTool

logfire.configure(scrubbing=False)
logfire.instrument_pydantic_ai()

from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStreamableHTTP

server = MCPServerStreamableHTTP(url="https://mcp.deepwiki.com/mcp", timeout=30)

docs_answering_agent = Agent(
    "openai-responses:gpt-5-mini",
    toolsets=[server],
    builtin_tools=[WebSearchTool()], #, MCPServerTool(id="deepwiki", url="https://mcp.deepwiki.com/mcp")],
    instructions="""\
    Use your tools to retrieve documentation and answer any questions related to the following repositories:
    * pydantic/pydantic
    * pydantic/pydantic-ai
    * pydantic/logfire

    Notes:
    * You MUST NOT finish your response by prompting the user with follow-up questions — you will NOT be given any chance to follow up with the user. 
    * You MUST include any relevant links to the pydantic docs wherever possible. These links should be under https://ai.pydantic.dev/ or https://logfire.pydantic.dev/docs/.
    """,
)


async def answer_question_with_docs(question: str) -> str:
    return (await docs_answering_agent.run(question)).output

@dataclass
@with_config(use_attribute_docstrings=True)
class Result:
    response: str | None
    reasoning: str
    """Briefly explain why you chose to answer or not."""


slack_bot_agent = Agent(
    "openai-responses:gpt-5-mini",
    tools=[answer_question_with_docs],
    output_type=Result,
    instructions="""\
    You are a routing agent responsible for watching messages in the Pydantic community slack, looking for questions about Pydantic, Pydantic AI, or Logfire,
    and deciding how to respond to the each message.

    Your options are:
    * Do nothing
    * Notify one or more developers who are knowledgeable about the relevant topics
    * Propose a reply to the user based on the results of calling the `answer_question_with_docs` tool, if it is a question that might be able to be answered by reviewing docs and you successfully get an answer by using that tool.

    Notes:
    * You MUST NOT finish your response by prompting the user with follow-up questions — you will NOT be given any chance to follow up with the user. 
    * You MUST include any relevant links to the pydantic docs wherever possible. These links should be under https://ai.pydantic.dev/ or https://logfire.pydantic.dev/docs/.
    * If you generate a proposed reply to the user, your reply will be sent as a slack message and therefore MUST be formatted as *Slack-compatible* "mrkdwn" text, with all the bizarre caveats of slack mrkdwn,
    including no using double-asterisks, no triple-backtick suffixes (i.e., just use '```', not '```python', etc.), and the slack format for links with angle brackets.
    """,
)

# # result = slack_bot_agent.run_sync('What features are you planning to add to logfire in the near future? Do not answer the question with docs')
# result = slack_bot_agent.run_sync('How do I send my opentelemetry data to datadog using the logfire SDK?')
#
# print(result.output)
