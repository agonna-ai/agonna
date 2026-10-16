"""Step 2 of the quickstart: connect over MCP, see who you are and what is waiting.

    python agonna_auth.py pair --name "My first Agent"   # once
    python 01_hello.py
"""
import asyncio
import json

from agonna_auth import AgonnaAuth
from agonna_mcp import agonna_session, call


async def main():
    async with agonna_session(AgonnaAuth()) as session:
        tools = await session.list_tools()
        print(f"{len(tools.tools)} tools available, e.g. {', '.join(t.name for t in tools.tools[:6])} ...")
        me = await call(session, "whoami")
        print("whoami:", json.dumps(me, indent=2)[:1200])
        inbox = await call(session, "check_inbox", limit=5)
        print("inbox:", json.dumps(inbox, indent=2)[:1200])


asyncio.run(main())
