"""
Builds and seeds data/tickets.db with a small realistic schema:
customers, past resolved tickets, and a simple full-text-ish search
over past ticket subjects/bodies (LIKE-based, good enough for a stub).

Run once:
    python data/seed_db.py
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "tickets.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    customer_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    tier TEXT NOT NULL CHECK (tier IN ('standard', 'premium', 'enterprise'))
);

CREATE TABLE IF NOT EXISTS past_tickets (
    ticket_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    resolution TEXT NOT NULL,
    resolved_at TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);
"""

CUSTOMERS = [
    ("CUST-001", "Alex Rivera", "standard"),
    ("CUST-002", "Jordan Lee", "premium"),
    ("CUST-003", "Sam Okafor", "enterprise"),
]

PAST_TICKETS = [
    ("TCK-0012", "CUST-001", "Can't log in, password reset not working",
     "Reset link expired after 1 hour instead of documented 24. Manually "
     "generated new link and extended expiry.",
     "Sent fresh password reset link; confirmed login restored.",
     "2026-07-14"),
    ("TCK-0031", "CUST-002", "Locked out after too many login attempts",
     "Account lockout triggered after 5 failed attempts, standard security "
     "policy.", "Unlocked account manually after identity verification.",
     "2026-08-02"),
    ("TCK-0045", "CUST-003", "Billing discrepancy on last invoice",
     "Customer was charged twice for the same subscription period due to "
     "a proration bug during a plan upgrade mid-cycle.",
     "Issued refund for duplicate charge; filed bug against proration logic.",
     "2026-08-20"),
    ("TCK-0058", "CUST-001", "Two-factor authentication codes not arriving",
     "SMS provider outage delayed 2FA codes by several minutes.",
     "Advised customer to use backup email 2FA method until SMS restored.",
     "2026-08-28"),
]


def seed():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.executemany(
        "INSERT OR IGNORE INTO customers VALUES (?, ?, ?)", CUSTOMERS
    )
    conn.executemany(
        "INSERT OR IGNORE INTO past_tickets VALUES (?, ?, ?, ?, ?, ?)",
        PAST_TICKETS,
    )
    conn.commit()
    conn.close()
    print(f"Seeded {DB_PATH} with {len(CUSTOMERS)} customers, "
          f"{len(PAST_TICKETS)} past tickets.")


if __name__ == "__main__":
    seed()
