
import logfire
from pydantic_ai import WebSearchTool

logfire.configure(scrubbing=False)
logfire.instrument_pydantic_ai()

from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStreamableHTTP

server = MCPServerStreamableHTTP(url="https://mcp.deepwiki.com/mcp", timeout=30)

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
    """,
)
