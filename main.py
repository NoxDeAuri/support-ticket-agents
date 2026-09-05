"""
Orchestrator — through Day 7, with a --provider feature flag, a
rich-based live terminal UI (see display.py), and an interactive mode
for typing in your own ticket.

router: real LLM call (sync)
retrieval: real LLM call + MCP client call to mcp_server.py (async)
action: real LLM call (sync)

Provider selection precedence: --provider flag > LLM_PROVIDER env var
> "ollama" default (see config.py).

Run:
    python main.py                        # sample tickets, live UI
    python main.py --interactive          # type your own ticket
    python main.py --provider anthropic   # requires ANTHROPIC_API_KEY set
    python main.py --plain                # plain text output, no rich UI
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
    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Type in your own ticket instead of running the sample tickets.",
    )
    return parser.parse_args()


_args = parse_args()
if _args.provider is not None:
    config.set_provider(_args.provider)

# Safe to import agents (and therefore llm_client) only past this point.
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

    display.show_ticket_header(ticket_id, subject, body, customer_id)

    with display.step_spinner("router") as t:
        message = router.route(message)
    display.show_step_result("router", message["history"][-1], t["elapsed"])

    with display.step_spinner("retrieval") as t:
        message = await retrieval.retrieve(message)
    display.show_step_result("retrieval", message["history"][-1], t["elapsed"])
    display.show_retrieved_context(message["context"])

    with display.step_spinner("action") as t:
        message = action.act(message)
    display.show_step_result("action", message["history"][-1], t["elapsed"])

    display.show_final_summary(message)
    return message


EXAMPLE_TICKET = {
    "subject": "Forgot password and reset email never arrived",
    "body": ("I requested a password reset three times in the last hour "
             "but the email never shows up, not even in spam. I need to "
             "get into my account today."),
    "customer_id": "CUST-001",
}


def prompt_for_ticket() -> dict:
    """
    Collects a ticket interactively. Kept as plain input() calls
    (not rich.prompt) so this still works identically under --plain
    and doesn't add another dependency for something this simple.

    Offers a ready-made example first so --interactive doesn't drop
    someone straight into a blank prompt with nothing to go on — the
    example is picked to match a ticket already in the seeded DB
    (data/seed_db.py), so accepting it demonstrates the "similar past
    ticket found" context display, not just an empty-context escalation.
    """
    print("\nExample ticket:")
    print(f"  Subject: {EXAMPLE_TICKET['subject']}")
    print(f"  Body: {EXAMPLE_TICKET['body']}")
    print(f"  Customer ID: {EXAMPLE_TICKET['customer_id']}")
    choice = input("\nPress Enter to run this example, or type 'c' to write "
                    "your own ticket: ").strip().lower()

    if choice != "c":
        return {"ticket_id": "TCK-INTERACTIVE", **EXAMPLE_TICKET}

    print("\nEnter your own support ticket (Ctrl+C to cancel):\n")
    subject = input("Subject: ").strip()
    print("Body (press Enter twice to finish):")
    body_lines = []
    while True:
        line = input()
        if line == "" and (not body_lines or body_lines[-1] == ""):
            break
        body_lines.append(line)
    body = "\n".join(body_lines).strip()
    customer_id = input("Customer ID (optional, e.g. CUST-001, or leave blank): ").strip()

    return {
        "ticket_id": "TCK-INTERACTIVE",
        "subject": subject or "(no subject provided)",
        "body": body or "(no body provided)",
        "customer_id": customer_id or None,
    }


async def main():
    plain = _args.plain
    if plain:
        print(f"Running with LLM_PROVIDER={config.get_provider()!r}\n")
    else:
        display.console.print(
            f"[dim]Running with LLM_PROVIDER={config.get_provider()!r}[/dim]"
        )

    if _args.interactive:
        ticket = prompt_for_ticket()
        result = await run_pipeline(**ticket, plain=plain)
        if plain:
            print(f"\n=== {result['ticket_id']} ===")
            print(f"Final status: {result['status']}")
            print(f"Resolution:   {result['resolution']}")
        return

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
