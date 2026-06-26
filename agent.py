"""agent.py — the bare reason->act->observe loop (Forge-Gap S1).

The ugliest end-to-end agent loop, built directly on `glm.chat()`:

    reason   -> ask GLM what to do next (it may emit a tool call)
    act      -> execute the tool GLM asked for
    observe  -> feed the tool's result back, then loop

It has ONE hardcoded tool (`get_weather`) and ZERO reliability mechanisms — no
retry, no error-recovery, no validate-and-correct. When a step breaks, the loop
records it honestly and moves on (or stops). That bareness is the whole point:
later sessions layer guardrails on top and *measure* how much they help.

The 3 places a single step can fail *mechanically* — i.e. the machinery of a
step broke, not "GLM couldn't think." These are exactly what the guardrails target:

  1. REASON   — GLM emits no tool call when one is needed, names a tool that does
                not exist, or emits arguments that aren't valid JSON / don't match
                the schema. (The decision-to-act is malformed.)
  2. ACT      — the tool dispatches but execution fails: bad input, an exception,
                a 404 from a real service. (The action itself errors.)
  3. OBSERVE  — the result comes back but the loop never converges: GLM can't use
                the observation and the run hits max_steps with no final answer.
                (The feedback loop fails to close.)

Every step is appended as one JSON line to `trajectory.jsonl` — the run header,
each reason/act/observe, and the final answer — so a human can hand-read exactly
where a run went wrong. That hand-read is the input to the S3 failure triage.

Run:  uv run agent.py
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from glm import MODEL, chat

# --- config ---------------------------------------------------------------
TASK = (
    "What's the current weather in Tokyo? "
    "Use the get_weather tool, then answer me in one sentence."
)
MAX_STEPS = 6        # generous; the happy path resolves in 2 reasoning turns.
TEMPERATURE = 0.7    # Non-zero on purpose. We never fake determinism via temp 0 —
                     # GLM is stochastic regardless; signal comes from N, not temp.
                     # We always record the temperature we used (see the run header).
TRAJECTORY_PATH = "trajectory.jsonl"

SYSTEM_PROMPT = (
    "You are a helpful assistant with access to tools. "
    "When a tool can answer the user's question, call it; "
    "then reply to the user in a single sentence."
)


# --- the one hardcoded tool ----------------------------------------------
def get_weather(city: str) -> str:
    """The single tool for S1. Deterministic fake — there is no real weather API.

    A canned string keeps S1 free of network flakiness so the *loop*, not the
    tool, is what we exercise. (S2 swaps this for the real lookup-then-compute
    scenario tools plus a deterministic oracle.)
    """
    return f"The weather in {city} is 18°C and partly cloudy."


# OpenAI-style tool schema that GLM sees. One tool, one required arg.
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

TOOLS = [WEATHER_TOOL]
REGISTRY = {"get_weather": get_weather}  # tool name -> python callable


# --- act: dispatch a single tool call ------------------------------------
def dispatch(name: str, args: dict) -> tuple[bool, str]:
    """Run tool `name` with `args`; return (ok, result_or_error_string).

    Pure and synchronous, so it's trivially testable without the network.
    ZERO mechanisms: on any failure we report it and return — no retry, no
    repair. The honest error string is what gets fed back as the observation.
    """
    fn = REGISTRY.get(name)
    if fn is None:
        return False, f"unknown tool: {name!r}"
    try:
        return True, fn(**args)
    except Exception as exc:  # noqa: BLE001 — a tool error is an observation, not a crash
        return False, f"{type(exc).__name__}: {exc}"


# --- the loop -------------------------------------------------------------
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run(
    task: str = TASK,
    *,
    max_steps: int = MAX_STEPS,
    temperature: float = TEMPERATURE,
    out_path: str = TRAJECTORY_PATH,
) -> dict:
    """Run one reason->act->observe loop to completion, logging every step.

    Returns a small summary dict; writes the full trajectory to `out_path`.
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task},
    ]
    records: list[dict] = []

    def log(rec: dict) -> None:
        records.append(rec)

    log({
        "event": "run", "ts": _now(), "model": MODEL,
        "temperature": temperature, "max_steps": max_steps, "task": task,
    })

    stop = "max_steps"   # overwritten to "completed" once GLM gives a final answer
    final_answer: str | None = None
    prompt_tokens = completion_tokens = 0

    for step in range(max_steps):
        resp = chat(messages, tools=TOOLS, tool_choice="auto", temperature=temperature)
        choice = resp.choices[0]
        msg = choice.message
        usage = resp.usage
        if usage:
            prompt_tokens += usage.prompt_tokens
            completion_tokens += usage.completion_tokens

        calls = msg.tool_calls or []

        # REASON — record what GLM decided this turn.
        log({
            "event": "reason", "step": step,
            "content": msg.content,
            "finish_reason": choice.finish_reason,
            "tool_calls": [
                {"id": c.id, "name": c.function.name,
                 "arguments_raw": c.function.arguments}
                for c in calls
            ],
            "usage": ({"prompt": usage.prompt_tokens,
                       "completion": usage.completion_tokens} if usage else None),
        })

        if not calls:
            # No tool call -> GLM is answering directly. Treat as the final answer.
            stop, final_answer = "completed", msg.content
            log({"event": "final", "step": step, "stop": stop, "answer": final_answer})
            break

        # Thread GLM's tool-call message back into the conversation verbatim.
        messages.append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [
                {"id": c.id, "type": "function",
                 "function": {"name": c.function.name,
                              "arguments": c.function.arguments}}
                for c in calls
            ],
        })

        for c in calls:
            # Parse the args. Malformed JSON is a REASON-phase mechanical failure.
            try:
                args = json.loads(c.function.arguments)
                args_ok = True
            except json.JSONDecodeError:
                args, args_ok = {}, False

            # ACT — dispatch the tool (or record why we couldn't).
            if not args_ok:
                ok, result = False, f"malformed JSON arguments: {c.function.arguments!r}"
            else:
                ok, result = dispatch(c.function.name, args)
            log({
                "event": "act", "step": step, "tool_call_id": c.id,
                "tool": c.function.name, "args": args,
                "args_ok": args_ok, "dispatch_ok": ok,
            })

            # OBSERVE — feed the outcome (result OR error) back to GLM verbatim.
            log({"event": "observe", "step": step, "tool_call_id": c.id,
                 "ok": ok, "result": result})
            messages.append({"role": "tool", "tool_call_id": c.id, "content": result})
    else:
        # Loop exhausted with no final answer -> OBSERVE-phase failure to converge.
        log({"event": "final", "step": max_steps - 1, "stop": stop, "answer": None})

    with open(out_path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return {
        "stop": stop,
        "final_answer": final_answer,
        "reasoning_turns": sum(1 for r in records if r["event"] == "reason"),
        "tokens": {"prompt": prompt_tokens, "completion": completion_tokens},
        "trajectory": out_path,
        "records": len(records),
    }


def main() -> int:
    print(f"Running reason->act->observe loop  (model={MODEL}, temp={TEMPERATURE})")
    print(f"Task: {TASK}\n")
    s = run()
    print("-" * 60)
    print(f"stop           : {s['stop']}")
    print(f"reasoning turns: {s['reasoning_turns']}")
    print(f"final answer   : {s['final_answer']!r}")
    print(f"tokens         : prompt={s['tokens']['prompt']} "
          f"completion={s['tokens']['completion']}")
    print(f"trajectory     : {s['trajectory']} ({s['records']} records)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
