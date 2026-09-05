"""
Data access layer / "tools" for the retrieval agent.

Kept as plain functions (not classes) so they can be exposed directly
as MCP tools in Day 6 with minimal wrapping.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "tickets.db"


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def find_similar_past_tickets(keywords: str, limit: int = 3) -> list[dict]:
    """
    Naive keyword search over past ticket subject/body. Good enough for
    a stub; a real system would use embeddings + vector search here.
    """
    conn = _connect()
    like_pattern = f"%{keywords}%"
    rows = conn.execute(
        """
        SELECT ticket_id, subject, resolution
        FROM past_tickets
        WHERE subject LIKE ? OR body LIKE ?
        LIMIT ?
        """,
        (like_pattern, like_pattern, limit),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_customer_tier(customer_id: str) -> str | None:
    conn = _connect()
    row = conn.execute(
        "SELECT tier FROM customers WHERE customer_id = ?", (customer_id,)
    ).fetchone()
    conn.close()
    return row["tier"] if row else None
