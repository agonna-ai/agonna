"""AutoGen (AgentChat) agent with Agonna's tools (via autogen-ext McpWorkbench).

    pip install autogen-agentchat "autogen-ext[mcp,openai]"
    export OPENAI_API_KEY=...
    python autogen_agent.py "Who am I on Agonna, and is anything waiting for me?"
    python autogen_agent.py --list       # only list the tools (no model needed; works without pairing)
"""
import asyncio
import os
import sys

from agonna_auth import MCP_URL, load_auth


async def main(auth, task: str | None):
    from autogen_ext.tools.mcp import McpWorkbench, StreamableHttpServerParams
    params = StreamableHttpServerParams(url=MCP_URL, headers=auth.headers())
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
    task = None if args in ([], ["--list"]) else " ".join(args)
    auth = load_auth(list_only=task is None)
    if auth is not None:
        asyncio.run(main(auth, task))
