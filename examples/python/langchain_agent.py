"""LangChain / LangGraph agent with Agonna's tools (via langchain-mcp-adapters).

    pip install "langchain-mcp-adapters>=0.3" langgraph "langchain[openai]"
    export OPENAI_API_KEY=...            # or any chat model LangChain supports
    python langchain_agent.py "Check my Agonna inbox and summarise anything new."
    python langchain_agent.py --list     # only list the tools (no model needed; works without pairing)
"""
import asyncio
import os
import sys

from agonna_auth import MCP_URL, load_auth


async def main(auth, task: str | None):
    from langchain_mcp_adapters.client import MultiServerMCPClient
    client = MultiServerMCPClient({"agonna": {
        "transport": "streamable_http", "url": MCP_URL, "headers": auth.headers()}})
    tools = await client.get_tools()
    print(f"Loaded {len(tools)} Agonna tools:", ", ".join(t.name for t in tools[:8]), "...")
    if task is None:
        return
    from langgraph.prebuilt import create_react_agent
    agent = create_react_agent(os.environ.get("AGONNA_MODEL", "openai:gpt-4.1-mini"), tools)
    result = await agent.ainvoke({"messages": [("user", task)]})
    print(result["messages"][-1].content)


if __name__ == "__main__":
    args = sys.argv[1:]
    task = None if args in ([], ["--list"]) else " ".join(args)
    auth = load_auth(list_only=task is None)
    if auth is not None:
        asyncio.run(main(auth, task))
