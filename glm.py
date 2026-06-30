"""Minimal GLM-via-OpenRouter client.

This is the foundation to build harnesses around: a thin wrapper over the
OpenRouter Chat Completions API (which is OpenAI-compatible) pointed at GLM-4.6.

    from glm import chat, MODEL
    resp = chat([{"role": "user", "content": "hi"}])
    print(resp.choices[0].message.content)

Pass `tools=[...]` / `tool_choice=...` straight through `chat(...)` for tool-calling.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()  # load forge-gap/.env into the environment

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MODEL = os.getenv("OPENROUTER_MODEL", "z-ai/glm-4.6")

# Optional OpenRouter attribution headers (they show up on your activity page).
_DEFAULT_HEADERS = {
    "HTTP-Referer": os.getenv("OPENROUTER_APP_URL", "https://localhost/forge-gap"),
    "X-Title": os.getenv("OPENROUTER_APP_TITLE", "forge-gap"),
}


def client() -> OpenAI:
    """Return an OpenAI SDK client pointed at OpenRouter.

    Fails loudly with a setup hint if the key is missing, so a broken .env is
    obvious instead of producing a confusing 401 deep in your code.
    """
    key = os.getenv("OPENROUTER_API_KEY")
    if not key or "REPLACE" in key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Put your key in forge-gap/.env "
            "(see README.md -> 'Get your key')."
        )
    return OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=key,
        default_headers=_DEFAULT_HEADERS,
        # Provider rate-limits (429) and transient 5xx are common on cheap/shared OpenRouter routes;
        # let the SDK ride them out with exponential backoff so a blip doesn't abort a whole N-trial
        # arm (runner.run_arm has no per-trial guard). This is API/infra hygiene (like MAX_TOKENS) at
        # the HTTP layer — NOT the experiment's error-recovery arm, which retries *tool* faults.
        max_retries=8,
    )


def chat(messages, *, model: str | None = None, **kwargs):
    """One-shot chat completion. Returns the full response object.

    `kwargs` are forwarded to the API (e.g. tools, tool_choice, temperature,
    max_tokens), so this stays useful as the harness grows.
    """
    return client().chat.completions.create(
        model=model or MODEL,
        messages=messages,
        **kwargs,
    )
