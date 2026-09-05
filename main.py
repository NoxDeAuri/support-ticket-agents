"""
Orchestrator — through Day 7, with a --provider feature flag and a
rich-based live terminal UI (see display.py).

router: real LLM call (sync)
retrieval: real LLM call + MCP client call to mcp_server.py (async)
action: real LLM call (sync)

Provider selection precedence: --provider flag > LLM_PROVIDER env var
> "ollama" default (see config.py).

Run:
    python main.py                        # uses LLM_PROVIDER env var, or ollama default
    python main.py --provider ollama       # explicit local/free
    python main.py --provider anthropic    # requires ANTHROPIC_API_KEY set
    python main.py --plain                 # plain text output, no rich UI (useful for logs/CI)
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
    parser.add_argument(
        "--plain",
        action="store_true",
        help="Plain text output instead of the rich live terminal UI "
             "(useful for logs, CI, or piping output).",
    )
    return parser.parse_args()


_args = parse_args()
if _args.provider is not None:
    config.set_provider(_args.provider)

# Safe to import agents (and therefore llm_client) only past this point.
import time

from schema import new_ticket_message
from agents import router, retrieval, action
import display


async def run_pipeline(ticket_id: str, subject: str, body: str,
                        customer_id: str | None = None,
                        plain: bool = False) -> dict:
    message = new_ticket_message(ticket_id, subject, body)
    if customer_id:
        message["customer_id"] = customer_id

    if plain:
        message = router.route(message)
        message = await retrieval.retrieve(message)
        message = action.act(message)
        return message

    display.show_ticket_header(ticket_id, subject)

    with display.step_spinner("router") as t:
        message = router.route(message)
    display.show_step_result("router", message["history"][-1], t["elapsed"])

    with display.step_spinner("retrieval") as t:
        message = await retrieval.retrieve(message)
    display.show_step_result("retrieval", message["history"][-1], t["elapsed"])

    with display.step_spinner("action") as t:
        message = action.act(message)
    display.show_step_result("action", message["history"][-1], t["elapsed"])

    display.show_final_summary(message)
    return message


async def main():
    plain = _args.plain
    if plain:
        print(f"Running with LLM_PROVIDER={config.get_provider()!r}\n")
    else:
        display.console.print(
            f"[dim]Running with LLM_PROVIDER={config.get_provider()!r}[/dim]"
        )

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

    results = []
    for ticket in sample_tickets:
        result = await run_pipeline(**ticket, plain=plain)
        results.append(result)

        if plain:
            print(f"\n=== {result['ticket_id']} ===")
            print(f"Final status: {result['status']}")
            print(f"Resolution:   {result['resolution']}")
            print("Handoff trail:")
            for step in result["history"]:
                print(f"  [{step['agent']:9}] {step['action']} — {step['detail']}")

    if not plain:
        display.show_run_summary(results)


if __name__ == "__main__":
    asyncio.run(main())
