"""
Terminal UI for the pipeline, using rich.

Purpose: replace the wall-of-text-at-the-end output with live,
step-by-step visibility — a spinner while each agent works, an
immediately-printed result line with real timing once it finishes,
and a boxed summary panel per ticket. Built specifically so a
screen-recorded demo shows *something happening*, not a silent pause
followed by a text dump.

This module has no LLM/business logic in it — it's purely
presentation, kept separate so agents/* and main.py's orchestration
logic stay testable without a terminal.
"""

import time
from contextlib import contextmanager

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()

# Maps a step's "action" value (from schema.log_step) to a display
# style — used for both the inline step line and border colors.
_STATUS_STYLES = {
    "resolved": "bold green",
    "escalated": "bold yellow",
    "direct_escalation": "bold yellow",
    "needs_retrieval": "cyan",
    "fetched_context": "cyan",
    "routed": "cyan",
    "retrieved": "cyan",
}


def show_ticket_header(ticket_id: str, subject: str) -> None:
    console.print()
    console.rule(f"[bold blue]{ticket_id}[/bold blue] — {subject}")


@contextmanager
def step_spinner(agent_name: str):
    """
    Shows a live spinner while the wrapped code runs, and yields a
    dict that the caller fills with 'elapsed' after the block exits —
    rich's status context doesn't hand back timing on its own.

    Usage:
        with step_spinner("router") as timing:
            message = router.route(message)
        show_step_result("router", message["history"][-1], timing["elapsed"])
    """
    timing = {}
    start = time.perf_counter()
    with console.status(f"[bold cyan]{agent_name}[/bold cyan] working...",
                          spinner="dots"):
        yield timing
    timing["elapsed"] = time.perf_counter() - start


def show_step_result(agent_name: str, step: dict, elapsed: float) -> None:
    style = _STATUS_STYLES.get(step.get("action", ""), "white")
    detail = (step.get("detail") or "")[:80]
    console.print(
        f"  [dim]{elapsed * 1000:5.0f}ms[/dim]  "
        f"[{style}]{agent_name:10}[/{style}] -> {step.get('action', ''):20} "
        f"[dim]{detail}[/dim]"
    )


def show_final_summary(message: dict) -> None:
    status = message.get("status", "unknown")
    style = _STATUS_STYLES.get(status, "white")
    border = style.split()[-1] if style else "white"

    body = Text()
    body.append("Status: ", style="bold")
    body.append(f"{status}\n", style=style)
    body.append("Resolution: ", style="bold")
    body.append(f"{message.get('resolution', '')}\n")

    console.print(Panel(
        body,
        title=f"{message.get('ticket_id', '')} — Final Result",
        border_style=border,
    ))


def show_run_summary(results: list[dict]) -> None:
    """One table across all tickets processed in this run."""
    table = Table(title="Run Summary")
    table.add_column("Ticket")
    table.add_column("Status")
    table.add_column("Steps")

    for r in results:
        status = r.get("status", "unknown")
        style = _STATUS_STYLES.get(status, "white")
        step_summary = " → ".join(s["action"] for s in r.get("history", []))
        table.add_row(r.get("ticket_id", ""), f"[{style}]{status}[/{style}]",
                      step_summary)

    console.print()
    console.print(table)
