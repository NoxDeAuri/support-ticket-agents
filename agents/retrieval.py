"""
Retrieval agent (Day 6 — via MCP instead of direct import).

Same job as Day 5: extract search keywords with an LLM call, then
fetch context. The fetch now goes through the MCP client, which talks
to mcp_server.py over stdio rather than importing data/tools.py in-
process. This is what lets the data layer become a genuinely separate
service later without changing this agent's code.
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from schema import log_step
from llm_client import call_llm_json
from sanitize import wrap_untrusted, INJECTION_DEFENSE_INSTRUCTION
import mcp_client

SYSTEM_PROMPT = f"""You extract search keywords from a support ticket
so a downstream system can search past tickets for similar issues.

{INJECTION_DEFENSE_INSTRUCTION}

Respond with ONLY a JSON object, no other text:
{{
  "keywords": "<2-4 words that best capture the core issue>"
}}

Prefer the underlying problem over specific details — e.g. use
"password reset" not "password reset link expired Tuesday"."""

MCP_MAX_RETRIES = 2


async def _call_mcp_with_retry(coro_fn, *args, max_retries: int = MCP_MAX_RETRIES):
    """
    MCP calls fail for infra reasons (subprocess didn't start cleanly,
    transient stdio hiccup) rather than bad input, so a plain retry
    with backoff is the right strategy here — unlike the LLM JSON
    retry, which needs to change the prompt, not just resend it.
    """
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return await coro_fn(*args)
        except Exception as e:  # noqa: BLE001 - deliberately broad: any
                                  # MCP/subprocess/transport failure should
                                  # trigger the same retry-then-fallback path
            last_exc = e
            if attempt < max_retries:
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
    raise ConnectionError(
        f"MCP call to {coro_fn.__name__} failed after "
        f"{max_retries + 1} attempts: {last_exc}"
    ) from last_exc


async def retrieve(message: dict) -> dict:
    user_prompt = (
        f"Subject: {wrap_untrusted(message['subject'])}\n"
        f"Body: {wrap_untrusted(message['body'])}"
    )

    try:
        result = call_llm_json(SYSTEM_PROMPT, user_prompt)
        keywords = result.get("keywords", message["subject"])
    except ValueError:
        # LLM couldn't produce valid JSON even after its own retries —
        # fall back to the raw subject line as the search term rather
        # than failing the whole pipeline over a keyword-extraction miss.
        keywords = message["subject"]

    try:
        similar = await _call_mcp_with_retry(
            mcp_client.search_past_tickets, keywords
        )
    except ConnectionError:
        # Data layer is unreachable — proceed with no context rather
        # than crashing. Downstream action agent must escalate when
        # similar_past_tickets is empty (see agents/action.py).
        similar = []

    customer_id = message.get("customer_id")
    tier = None
    if customer_id:
        try:
            tier = await _call_mcp_with_retry(
                mcp_client.lookup_customer_tier, customer_id
            )
        except ConnectionError:
            tier = None

    message["context"] = {
        "search_keywords_used": keywords,
        "similar_past_tickets": similar,
        "customer_tier": tier,
    }
    message["status"] = "retrieved"
    log_step(message, agent="retrieval", action="fetched_context",
              detail=f"searched via MCP on '{keywords}', found "
                     f"{len(similar) if isinstance(similar, list) else 0} match(es)")
    return message
