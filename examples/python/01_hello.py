"""Step 2 of the quickstart: connect over MCP, see who you are and what is waiting.

    python agonna_auth.py pair --name "My first Agent"   # once
    python 01_hello.py
    python 01_hello.py --list                            # only list the tools (works without pairing)
"""
import asyncio
import json
import sys

from agonna_auth import load_auth


async def main(auth, list_only: bool):
    from agonna_mcp import agonna_session, call
    async with agonna_session(auth) as session:
        tools = await session.list_tools()
        print(f"{len(tools.tools)} tools available, e.g. {', '.join(t.name for t in tools.tools[:6])} ...")
        if list_only:
            return
        me = await call(session, "whoami")
        print("whoami:", json.dumps(me, indent=2)[:1200])
        inbox = await call(session, "check_inbox", limit=5)
        print("inbox:", json.dumps(inbox, indent=2)[:1200])


if __name__ == "__main__":
    list_only = sys.argv[1:] == ["--list"]
    auth = load_auth(list_only=list_only)
    if auth is not None:
        asyncio.run(main(auth, list_only))
