"""agent.py — the bare reason->act->observe loop + deterministic grading (forge-gap).

The ugliest end-to-end agent loop, built directly on `glm.chat()`:

    reason   -> ask GLM what to do next (it may emit a tool call)
    act      -> execute the tool GLM asked for
    observe  -> feed the tool's result back, then loop

The loop is scenario-agnostic: it drives whatever `Scenario` you hand `run()` (its
tools, registry, task, and known ground truth). The default is the S2 lookup-then-compute
task from `scenario.py` — chain two record lookups, then call `submit_answer` with the
total. There are ZERO reliability mechanisms — no retry, no error-recovery, no
validate-and-correct. When a step breaks, the loop records it honestly and moves on (or
stops). That bareness is the whole point: later sessions layer guardrails on top and
*measure* how much they help.

A run ends one of three ways, and a deterministic oracle (`oracle.py`, never an LLM)
grades the submitted answer against the scenario's known ground truth:

    submitted  -> GLM called the terminal tool (submit_answer); grade its value
    no_submit  -> GLM replied in prose without ever submitting
    max_steps  -> the loop ran out of steps before GLM submitted

The 3 places a single step can fail *mechanically* — i.e. the machinery of a step
broke, not "GLM couldn't think." These are exactly what the guardrails target:

  1. REASON   — GLM emits no tool call when one is needed, names a tool that does
                not exist, or emits arguments that aren't valid JSON / don't match
                the schema. (The decision-to-act is malformed.)
  2. ACT      — the tool dispatches but execution fails: bad input, an exception,
                a 404 from a real service. (The action itself errors.)
  3. OBSERVE  — the result comes back but the loop never converges: GLM can't use
                the observation and the run hits max_steps with no final answer.
                (The feedback loop fails to close.)

Every step is appended as one JSON line to `trajectory.jsonl` — the run header, each
reason/act/observe, the final answer, and the oracle's grade — so a human can hand-read
exactly where a run went wrong. That hand-read is the input to the S3 failure triage.

Run:  uv run agent.py
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from glm import MODEL, chat
from oracle import grade
from scenario import ORDER_SCENARIO, Scenario

# --- config ---------------------------------------------------------------
MAX_STEPS = 6        # generous; the happy path resolves in ~3 reasoning turns.
TEMPERATURE = 0.7    # Non-zero on purpose. We never fake determinism via temp 0 —
                     # GLM is stochastic regardless; signal comes from N, not temp.
                     # We always record the temperature we used (see the run header).
MAX_TOKENS = 2048    # Cap completion length per turn. Our turns run ~70-300 tokens, so this
                     # never truncates a real answer; it exists so OpenRouter reserves credits
                     # for 2048 tokens/call instead of its ~64k default — the unbounded default
                     # trips a 402 "insufficient credits" on a low balance even though actual
                     # spend is tiny. This is API/cost hygiene, NOT a reliability mechanism.
TRAJECTORY_PATH = "trajectory.jsonl"


# --- act: dispatch a single tool call ------------------------------------
def dispatch(name: str, args: dict, registry: dict) -> tuple[bool, str]:
    """Run tool `name` with `args` against `registry`; return (ok, result_or_error).

    Pure and synchronous, so it's trivially testable without the network. ZERO
    mechanisms: on any failure we report it and return — no retry, no repair. The
    honest error string is what gets fed back to GLM as the observation.
    """
    fn = registry.get(name)
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
    scenario: Scenario = ORDER_SCENARIO,
    *,
    model: str | None = None,
    max_steps: int = MAX_STEPS,
    temperature: float = TEMPERATURE,
    out_path: str = TRAJECTORY_PATH,
) -> dict:
    """Run one reason->act->observe loop to completion, then grade it.

    `model` overrides which model the loop calls (default: the env/`MODEL` default). That single
    knob is what lets one runner drive a GLM arm and a frontier arm through the *same* loop — the
    machinery is identical; only the model swaps. Returns a small summary dict (the oracle's
    correct/submitted/expected plus the model used); writes the full trajectory to `out_path`.
    """
    resolved_model = model or MODEL
    messages = [
        {"role": "system", "content": scenario.system_prompt},
        {"role": "user", "content": scenario.task},
    ]
    records: list[dict] = []

    def log(rec: dict) -> None:
        records.append(rec)

    log({
        "event": "run", "ts": _now(), "model": resolved_model, "scenario": scenario.name,
        "temperature": temperature, "max_steps": max_steps, "max_tokens": MAX_TOKENS,
        "task": scenario.task,
        "ground_truth": scenario.ground_truth,
    })

    stop = "max_steps"        # overwritten once GLM submits or stops talking
    final_answer = None
    submitted = None          # the value GLM passed to submit_answer (None if it never did)
    prompt_tokens = completion_tokens = 0

    for step in range(max_steps):
        resp = chat(messages, model=resolved_model, tools=scenario.tools,
                    tool_choice="auto", temperature=temperature, max_tokens=MAX_TOKENS)
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
            # No tool call -> GLM stopped without submitting. Its prose is the (ungraded) answer.
            stop, final_answer = "no_submit", msg.content
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

        terminated = False
        for c in calls:
            # Parse the args. Malformed JSON is a REASON-phase mechanical failure.
            try:
                args = json.loads(c.function.arguments)
                args_ok = True
            except json.JSONDecodeError:
                args, args_ok = {}, False

            # The terminal tool: capture GLM's final answer and stop. Never dispatched —
            # "submitting" can't fail mechanically, so dispatch_ok is trivially True; whether
            # the *value* is right is the oracle's call, made after the loop.
            if c.function.name == scenario.final_tool:
                submitted = args.get("value") if args_ok else None
                log({
                    "event": "act", "step": step, "tool_call_id": c.id,
                    "tool": c.function.name, "args": args,
                    "args_ok": args_ok, "dispatch_ok": True,
                })
                stop, final_answer, terminated = "submitted", submitted, True
                break

            # ACT — dispatch the tool (or record why we couldn't).
            if not args_ok:
                ok, result = False, f"malformed JSON arguments: {c.function.arguments!r}"
            else:
                ok, result = dispatch(c.function.name, args, scenario.registry)
            log({
                "event": "act", "step": step, "tool_call_id": c.id,
                "tool": c.function.name, "args": args,
                "args_ok": args_ok, "dispatch_ok": ok,
            })

            # OBSERVE — feed the outcome (result OR error) back to GLM verbatim.
            log({"event": "observe", "step": step, "tool_call_id": c.id,
                 "ok": ok, "result": result})
            messages.append({"role": "tool", "tool_call_id": c.id, "content": result})

        if terminated:
            break

    # GRADE — the deterministic oracle has the final word (never an LLM).
    correct, detail = grade(submitted, scenario.ground_truth)
    log({"event": "final", "step": step, "stop": stop, "answer": final_answer})
    log({
        "event": "grade", "submitted": submitted, "expected": scenario.ground_truth,
        "correct": correct, "reason": detail["reason"], "stop": stop,
    })

    with open(out_path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return {
        "scenario": scenario.name,
        "model": resolved_model,
        "stop": stop,
        "correct": correct,
        "submitted": submitted,
        "expected": scenario.ground_truth,
        "final_answer": final_answer,
        "reasoning_turns": sum(1 for r in records if r["event"] == "reason"),
        "tokens": {"prompt": prompt_tokens, "completion": completion_tokens},
        "trajectory": out_path,
        "records": len(records),
    }


def main() -> int:
    print(f"Running reason->act->observe loop  "
          f"(model={MODEL}, temp={TEMPERATURE}, scenario={ORDER_SCENARIO.name})")
    print(f"Task: {ORDER_SCENARIO.task}\n")
    s = run()
    verdict = "PASS" if s["correct"] else "FAIL"
    print("-" * 60)
    print(f"stop           : {s['stop']}")
    print(f"reasoning turns: {s['reasoning_turns']}")
    print(f"submitted      : {s['submitted']!r}   expected: {s['expected']!r}")
    print(f"oracle         : {verdict}")
    print(f"tokens         : prompt={s['tokens']['prompt']} "
          f"completion={s['tokens']['completion']}")
    print(f"trajectory     : {s['trajectory']} ({s['records']} records)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
