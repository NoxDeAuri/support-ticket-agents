"""
LLM client with a pluggable provider — defaults to Ollama (free, local,
no API key) so the whole project runs at zero cost. Anthropic remains
available as a drop-in swap by setting LLM_PROVIDER=anthropic.

Every agent calls call_llm() / call_llm_json() the same way regardless
of provider, so swapping providers never touches agents/*.py.

Setup for the default (Ollama) provider:
    1. Install: https://ollama.com/download
    2. Pull a model:  ollama pull llama3.1
    3. Ollama serves on http://localhost:11434 automatically after install
       (no need to run anything else — it starts a background service).
    4. Run the project as normal; no API key needed.

To use Anthropic instead:
    export LLM_PROVIDER=anthropic
    export ANTHROPIC_API_KEY=your-key-here
"""

import json
import os
import time

import config

LLM_PROVIDER = config.get_provider()  # "ollama" | "anthropic"
_DEFAULT_MODELS = {"ollama": "llama3.1", "anthropic": "claude-sonnet-4-6"}
MODEL = os.environ.get("LLM_MODEL", _DEFAULT_MODELS.get(LLM_PROVIDER, "llama3.1"))
DEFAULT_MAX_RETRIES = 2


def _build_client():
    if LLM_PROVIDER == "anthropic":
        import anthropic
        return anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    elif LLM_PROVIDER == "ollama":
        from openai import OpenAI
        # Ollama exposes an OpenAI-compatible endpoint; api_key is
        # unused but required by the client constructor, so any
        # placeholder string works.
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        return OpenAI(base_url=base_url, api_key="ollama")
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {LLM_PROVIDER!r} "
                          f"(expected 'ollama' or 'anthropic')")


_client = _build_client()


def call_llm(system: str, user: str, max_tokens: int = 500) -> str:
    """Single-turn call, returns the raw text response. Provider-agnostic."""
    if LLM_PROVIDER == "anthropic":
        response = _client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text

    elif LLM_PROVIDER == "ollama":
        response = _client.chat.completions.create(
            model=MODEL,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content


def call_llm_json(system: str, user: str, max_tokens: int = 500,
                   max_retries: int = DEFAULT_MAX_RETRIES) -> dict:
    """
    Calls the model expecting a JSON-only response and parses it.

    Retries on malformed JSON (the most common LLM failure mode for
    structured output, and *more* common on smaller local models than
    on Claude — worth knowing if you're benchmarking Ollama models)
    with a nudge appended to the prompt each retry. Raises ValueError
    with the last raw response if all attempts fail, so the caller can
    decide on a fallback (see agents/action.py).
    """
    last_raw = None
    current_user = user

    for attempt in range(max_retries + 1):
        raw = call_llm(system, current_user, max_tokens=max_tokens)
        last_raw = raw
        cleaned = (
            raw.strip()
            .removeprefix("```json").removeprefix("```")
            .removesuffix("```").strip()
        )
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            if attempt < max_retries:
                current_user = (
                    f"{user}\n\n(Your previous response was not valid JSON: "
                    f"{raw[:200]!r}. Respond with ONLY the JSON object, "
                    f"nothing else.)"
                )
                time.sleep(0.5 * (attempt + 1))  # small backoff
                continue

    raise ValueError(f"LLM did not return valid JSON after "
                      f"{max_retries + 1} attempts: {last_raw!r}")
