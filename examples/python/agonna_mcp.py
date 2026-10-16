"""Tiny helper: an MCP client session to Agonna using the official `mcp` Python SDK."""
from __future__ import annotations

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
    if result.isError:
        raise RuntimeError(f"{tool} failed: {' '.join(c.text for c in result.content if hasattr(c, 'text'))}")
    if result.structuredContent is not None:
        data = result.structuredContent
        return data.get("result", data) if isinstance(data, dict) and set(data) == {"result"} else data
    text = "".join(c.text for c in result.content if hasattr(c, "text"))
    try:
        return json.loads(text)
    except ValueError:
        return text
