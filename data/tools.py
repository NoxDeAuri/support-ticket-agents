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

    Splits on commas (and collapses whitespace) before matching, and
    tries each resulting term as its own OR clause, rather than one
    literal substring match on the whole input.

    This matters in practice, not just in theory: the caller
    (agents/retrieval.py) asks the model for "2-4 words," but a
    weaker/local model sometimes returns something like "password
    reset, expired link" instead of a single clean phrase. A single
    substring match on that entire string (including the comma) will
    essentially never exist verbatim in real data, even when the
    individual phrases clearly should have matched. Splitting and
    OR-ing the terms makes retrieval robust to that kind of model
    verbosity instead of silently returning zero results.
    """
    terms = [t.strip() for t in keywords.split(",") if t.strip()]
    if not terms:
        terms = [keywords.strip()] if keywords.strip() else []
    if not terms:
        return []

    conn = _connect()
    where_clauses = " OR ".join(["subject LIKE ? OR body LIKE ?"] * len(terms))
    params = []
    for term in terms:
        like_pattern = f"%{term}%"
        params.extend([like_pattern, like_pattern])
    params.append(limit)

    rows = conn.execute(
        f"""
        SELECT ticket_id, subject, resolution
        FROM past_tickets
        WHERE {where_clauses}
        LIMIT ?
        """,
        params,
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
