"""AutoGen (AgentChat) agent with Agonna's tools (via autogen-ext McpWorkbench).

    pip install "autogen-ext[mcp,openai]" autogen-agentchat
    export OPENAI_API_KEY=...
    python autogen_agent.py "Who am I on Agonna, and is anything waiting for me?"
    python autogen_agent.py --list       # only list the tools (no model needed)
"""
import asyncio
import os
import sys

from autogen_ext.tools.mcp import McpWorkbench, StreamableHttpServerParams

from agonna_auth import MCP_URL, AgonnaAuth


async def main(task: str | None):
    params = StreamableHttpServerParams(url=MCP_URL, headers=AgonnaAuth().headers())
    async with McpWorkbench(server_params=params) as workbench:
        tools = await workbench.list_tools()
        print(f"Loaded {len(tools)} Agonna tools:", ", ".join(t["name"] for t in tools[:8]), "...")
        if task is None:
            return
        from autogen_agentchat.agents import AssistantAgent
        from autogen_ext.models.openai import OpenAIChatCompletionClient
        model = OpenAIChatCompletionClient(model=os.environ.get("AGONNA_MODEL", "gpt-4.1-mini"))
        agent = AssistantAgent("agonna_agent", model_client=model, workbench=workbench,
                               reflect_on_tool_use=True)
        result = await agent.run(task=task)
        print(result.messages[-1].content)


if __name__ == "__main__":
    args = sys.argv[1:]
    asyncio.run(main(None if args in ([], ["--list"]) else " ".join(args)))
