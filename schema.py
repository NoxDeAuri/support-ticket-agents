"""
Shared message shape passed between agents.

Using plain dicts (per Day 1 scope) rather than Pydantic so the contract
stays visible and easy to print/debug while stubbing. Can swap to
Pydantic models later without changing the pipeline logic.
"""

from datetime import datetime, timezone


def new_ticket_message(ticket_id: str, subject: str, body: str) -> dict:
    """The initial message that kicks off the pipeline."""
    return {
        "ticket_id": ticket_id,
        "subject": subject,
        "body": body,
        "history": [],       # list of {"agent": str, "action": str, "detail": str}
        "context": {},        # populated by retrieval agent
        "status": "new",      # new -> routed -> retrieved -> resolved | escalated
        "resolution": None,   # set by action agent
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def log_step(message: dict, agent: str, action: str, detail: str = "") -> dict:
    """Every agent appends one of these before passing the message on."""
    message["history"].append({
        "agent": agent,
        "action": action,
        "detail": detail,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return message
