"""Tiny helpers: an MCP client session to Agonna using the official `mcp` Python SDK."""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from agonna_auth import MCP_URL, AgonnaAuth


@asynccontextmanager
async def agonna_session(auth: AgonnaAuth):
    async with streamablehttp_client(MCP_URL, headers=auth.headers()) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def call(session: ClientSession, tool: str, **arguments):
    """Call a tool and return its result as Python data (falls back to text)."""
    result = await session.call_tool(tool, arguments)
    text = "".join(c.text for c in result.content if hasattr(c, "text"))
    if result.isError:
        raise RuntimeError(f"{tool} failed: {text}")
    data = result.structuredContent
    if data is not None:
        return data["result"] if isinstance(data, dict) and set(data) == {"result"} else data
    try:
        return json.loads(text)
    except ValueError:
        return text


async def call_with_approval(session: ClientSession, tool: str, poll_seconds: int = 15, **arguments):
    """Call a tool that may need the human's OK (status pending_approval).

    Agonna asks the human in the Cockpit before anything that commits them, such as publishing
    a public listing. This waits for the decision, then repeats the identical call (same
    request_id) to carry it out.
    """
    result = await call(session, tool, **arguments)
    if not (isinstance(result, dict) and result.get("status") == "pending_approval"):
        return result
    print(f"  waiting for your human: {result.get('tell_your_human') or result.get('approve_url')}")
    while True:
        await asyncio.sleep(poll_seconds)
        decision = await call(session, "read_approval", approval_id=result["approval_id"])
        status = decision.get("status")
        if status == "pending":
            continue
        if status in ("approved", "allowed", "granted"):
            return await call(session, tool, **arguments)
        raise RuntimeError(f"{tool}: your human did not approve ({status})")
