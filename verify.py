"""Smoke-test the GLM-via-OpenRouter setup.

Two checks:
  1. A plain chat completion  -> is the key valid and does GLM-4.6 respond?
  2. A single tool-calling round-trip -> does GLM-4.6 emit a structured tool call?

Tool-calling is the heart of every harness, so we verify it now, not later.

Run with:  uv run verify.py
"""
from __future__ import annotations

import json
import sys

from glm import MODEL, chat


def check_chat() -> bool:
    print(f"[1/2] Plain chat completion  (model={MODEL}) ... ", end="", flush=True)
    resp = chat(
        [{"role": "user", "content": "Reply with exactly: harness online"}],
        max_tokens=20,
        temperature=0,
    )
    text = (resp.choices[0].message.content or "").strip()
    usage = resp.usage
    print("OK")
    print(f"      reply : {text!r}")
    print(f"      tokens: prompt={usage.prompt_tokens} completion={usage.completion_tokens}")
    return bool(text)


WEATHER_TOOL = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the current weather for a city.",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "City name"}},
            "required": ["city"],
        },
    },
}


def check_tool_call() -> bool:
    print("[2/2] Tool-calling round-trip ... ", end="", flush=True)
    resp = chat(
        [{"role": "user", "content": "What's the weather in Tokyo? Use the tool."}],
        tools=[WEATHER_TOOL],
        tool_choice="auto",
        temperature=0,
    )
    msg = resp.choices[0].message
    calls = msg.tool_calls or []
    if not calls:
        print("NO TOOL CALL")
        print(f"      model replied with text instead: {msg.content!r}")
        return False
    call = calls[0]
    args = json.loads(call.function.arguments)
    print("OK")
    print(f"      tool  : {call.function.name}")
    print(f"      args  : {args}")
    return call.function.name == "get_weather" and "city" in args


def main() -> int:
    print("Verifying GLM-via-OpenRouter setup\n" + "-" * 36)
    try:
        ok_chat = check_chat()
        print()
        ok_tool = check_tool_call()
    except Exception as e:  # noqa: BLE001 - friendly top-level message
        print("FAILED\n")
        print(f"Error: {type(e).__name__}: {e}")
        print("\nCommon causes:")
        print("  - Key missing / typo'd    -> check harness-lab/.env")
        print("  - No OpenRouter credits   -> add a few $ at openrouter.ai/credits")
        print("  - Model slug changed      -> check OPENROUTER_MODEL in .env")
        return 1

    print("\n" + "-" * 36)
    if ok_chat and ok_tool:
        print("All checks passed - GLM-4.6 chat + tool-calling work. Ready to build.")
        return 0
    print("Connected, but a check soft-failed (see above).")
    return 2


if __name__ == "__main__":
    sys.exit(main())
