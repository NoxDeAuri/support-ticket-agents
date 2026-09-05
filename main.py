"""
Orchestrator — through Day 7, with a --provider feature flag.

router: real LLM call (sync)
retrieval: real LLM call + MCP client call to mcp_server.py (async)
action: real LLM call (sync)

Provider selection precedence: --provider flag > LLM_PROVIDER env var
> "ollama" default (see config.py).

Run:
    python main.py                        # uses LLM_PROVIDER env var, or ollama default
    python main.py --provider ollama       # explicit local/free
    python main.py --provider anthropic    # requires ANTHROPIC_API_KEY set
"""

import argparse
import asyncio

import config

# --- CLI parsing must happen BEFORE importing anything that touches
# llm_client.py (that means schema.py is fine, but agents/* is not),
# because llm_client.py reads config.get_provider() once, at import
# time, to build its client. Importing agents/* earlier would lock in
# whatever the env var was at that point, silently ignoring --provider.


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run the support-ticket-agents pipeline."
    )
    parser.add_argument(
        "--provider",
        choices=config.VALID_PROVIDERS,
        default=None,
        help=f"LLM provider to use (default: LLM_PROVIDER env var, "
             f"or {config.DEFAULT_PROVIDER!r} if unset)",
    )
    return parser.parse_args()


_args = parse_args()
if _args.provider is not None:
    config.set_provider(_args.provider)

# Safe to import agents (and therefore llm_client) only past this point.
from schema import new_ticket_message
from agents import router, retrieval, action


async def run_pipeline(ticket_id: str, subject: str, body: str,
                        customer_id: str | None = None) -> dict:
    message = new_ticket_message(ticket_id, subject, body)
    if customer_id:
        message["customer_id"] = customer_id

    message = router.route(message)
    message = await retrieval.retrieve(message)
    message = action.act(message)

    return message


async def main():
    print(f"Running with LLM_PROVIDER={config.get_provider()!r}\n")

    sample_tickets = [
        {
            "ticket_id": "TCK-0101",
            "subject": "Can't log in — password not working",
            "body": "I've tried resetting my password twice, still locked out.",
            "customer_id": "CUST-001",
        },
        {
            "ticket_id": "TCK-0102",
            "subject": "Billing discrepancy on last invoice",
            "body": "I was charged twice for the same subscription period.",
            "customer_id": "CUST-003",
        },
    ]

    for ticket in sample_tickets:
        result = await run_pipeline(**ticket)
        print(f"\n=== {result['ticket_id']} ===")
        print(f"Final status: {result['status']}")
        print(f"Resolution:   {result['resolution']}")
        print("Handoff trail:")
        for step in result["history"]:
            print(f"  [{step['agent']:9}] {step['action']} — {step['detail']}")


if __name__ == "__main__":
    asyncio.run(main())
