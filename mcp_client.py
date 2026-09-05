"""
Day 6 — MCP client.

Spawns mcp_server.py as a subprocess over stdio and exposes its tools
as plain async Python functions, so the retrieval agent calls the
data layer through the MCP protocol instead of importing it directly.

A production version would keep a long-lived session across the whole
pipeline run rather than spawning per-call; this stub optimizes for
clarity over performance, matching the Day 6 scope.
"""

import json
import sys
from pathlib import Path
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER_PARAMS = StdioServerParameters(
    command=sys.executable,
    args=[str(Path(__file__).parent / "mcp_server.py")],
)


@asynccontextmanager
async def mcp_session():
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


def _parse_result(result) -> object:
    """
    MCP tool results come back as content blocks; unwrap to plain data.

    Per the MCP spec, non-object return types (lists, strings, etc.)
    get wrapped as {"result": <value>} in structured_content — unwrap
    that envelope so callers just get the list/string/etc. directly.
    """
    if result.structured_content is not None:
        content = result.structured_content
        if isinstance(content, dict) and set(content.keys()) == {"result"}:
            return content["result"]
        return content
    text = result.content[0].text if result.content else "null"
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


async def search_past_tickets(keywords: str, limit: int = 3) -> list[dict]:
    async with mcp_session() as session:
        result = await session.call_tool(
            "search_past_tickets", {"keywords": keywords, "limit": limit}
        )
        return _parse_result(result)


async def lookup_customer_tier(customer_id: str) -> str:
    async with mcp_session() as session:
        result = await session.call_tool(
            "lookup_customer_tier", {"customer_id": customer_id}
        )
        return _parse_result(result)
