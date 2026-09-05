"""
Feature flag: which LLM provider the pipeline uses.

This is deliberately a single, tiny module with no other project
imports, so it can be evaluated first — before agents/llm_client.py
builds its client — regardless of whether the flag comes from a CLI
arg or an environment variable.

Precedence: CLI flag (--provider) > LLM_PROVIDER env var > "ollama" default.
main.py resolves the CLI flag and calls set_provider() before importing
anything that touches llm_client.py; every other entry point (tests,
a future API server, etc.) can just rely on the env var directly.
"""

import os

VALID_PROVIDERS = ("ollama", "anthropic")
DEFAULT_PROVIDER = "ollama"


def get_provider() -> str:
    """Current provider, resolved from the environment."""
    provider = os.environ.get("LLM_PROVIDER", DEFAULT_PROVIDER)
    if provider not in VALID_PROVIDERS:
        raise ValueError(
            f"Invalid LLM_PROVIDER: {provider!r}. "
            f"Expected one of {VALID_PROVIDERS}."
        )
    return provider


def set_provider(provider: str) -> None:
    """
    Set the active provider. Must be called before llm_client.py (or
    anything importing it) is first imported, since llm_client builds
    its client once at import time — setting this after the fact has
    no effect on an already-imported client.
    """
    if provider not in VALID_PROVIDERS:
        raise ValueError(
            f"Invalid provider: {provider!r}. Expected one of {VALID_PROVIDERS}."
        )
    os.environ["LLM_PROVIDER"] = provider
