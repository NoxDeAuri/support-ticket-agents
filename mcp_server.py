"""
Day 6 — MCP server.

Exposes the retrieval agent's data tools (find_similar_past_tickets,
get_customer_tier) as proper MCP tools over stdio, instead of the
retrieval agent importing data/tools.py directly.

This is the piece that maps to what enterprise agentic-AI job listings
mean by "multi-agent coordination via MCP" — the tool boundary becomes
a real process/protocol boundary, not just a Python function call, so
it works the same whether the retrieval logic lives in-process or on
a separate service.

Run standalone to sanity check:
    python mcp_server.py
(it will just sit waiting for stdio input — Ctrl+C to exit. It's
normally launched automatically by mcp_client.py.)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from mcp.server.mcpserver import MCPServer
from data.tools import find_similar_past_tickets, get_customer_tier

mcp = MCPServer(name="support-ticket-data")


@mcp.tool()
def search_past_tickets(keywords: str, limit: int = 3) -> list[dict]:
    """Search past resolved tickets by keyword for similar issues."""
    return find_similar_past_tickets(keywords, limit=limit)


@mcp.tool()
def lookup_customer_tier(customer_id: str) -> str:
    """Look up a customer's support tier (standard/premium/enterprise)."""
    tier = get_customer_tier(customer_id)
    return tier if tier is not None else "unknown"


if __name__ == "__main__":
    mcp.run()
