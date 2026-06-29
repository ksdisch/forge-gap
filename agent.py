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
MAX_RECOVERIES = 3   # error-recovery arm only: how many times the HARNESS may transparently
                     # retry a transient tool failure within ONE act step (no model turn spent).
                     # Ignored by the bare baseline, whose run() default is recover=False.
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


# --- error-recovery: the S4 mechanism (a harness-level retry) --------------
# Transient/5xx-style signals worth a silent retry. We classify the *observation string* that
# dispatch already returns — NOT an exception type — so the core loop stays decoupled from any
# specific tool or fault module: the same predicate catches a real OpenRouter 503/429 and our
# injected ToolUnavailable alike. (Stringly-typed on purpose; HTTP status signalling already is.)
_RETRYABLE_HINTS = (
    "503", "temporarily unavailable", "toolunavailable",
    "timed out", "timeout", "429", "rate limit", "try again", "retry",
)


def _is_retryable(error: str) -> bool:
    """True if `error` looks like a transient failure a simple retry might clear."""
    e = error.lower()
    return any(hint in e for hint in _RETRYABLE_HINTS)


def dispatch_with_recovery(
    name: str, args: dict, registry: dict, *, recover: bool, max_recoveries: int
) -> tuple[bool, str, int]:
    """Dispatch `name`; if `recover`, transparently retry *transient* failures in-place.

    This is **error-recovery**, S4's first guardrail. The load-bearing contrast with the bare
    loop: a retry here happens INSIDE one act step, so it does NOT cost the model a reasoning
    turn. The bare baseline instead feeds the error back, and the model must spend a whole turn
    re-calling the tool itself — under heavy faults that exhausts the step budget (S3's `max_steps`
    misses). Only *retryable* errors are retried: a malformed call or an unknown-id KeyError is
    permanent, so re-calling it identically would just burn retries (those want retry-nudge or
    validation — different guardrails). Returns (ok, result_or_error, recoveries_used).
    """
    ok, result = dispatch(name, args, registry)
    recoveries = 0
    if recover:
        while (not ok) and _is_retryable(result) and recoveries < max_recoveries:
            recoveries += 1
            ok, result = dispatch(name, args, registry)
    return ok, result, recoveries


# --- retry-nudge: the S6 mechanism (an explicit corrective re-prompt) ------
def _nudge_message(failures: list[tuple[str, str]]) -> str:
    """Build retry-nudge's re-prompt: name each failed tool + its error and tell the model to
    fix-and-retry (not blindly repeat). The load-bearing contrast with error-recovery: this is a
    *model* turn — the model re-reasons and re-calls — so it can correct a MALFORMED call a blind
    harness retry never could, at the cost of one turn (DECISIONS D19)."""
    detail = "; ".join(f"{name}: {err}" for name, err in failures)
    return (
        f"Your last tool call failed — {detail}. "
        "Do not repeat the same call. Read the error, correct the arguments, and call the tool again."
    )


# --- the loop -------------------------------------------------------------
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run(
    scenario: Scenario = ORDER_SCENARIO,
    *,
    model: str | None = None,
    max_steps: int = MAX_STEPS,
    temperature: float = TEMPERATURE,
    recover: bool = False,
    max_recoveries: int = MAX_RECOVERIES,
    nudge: bool = False,
    out_path: str = TRAJECTORY_PATH,
) -> dict:
    """Run one reason->act->observe loop to completion, then grade it.

    `model` overrides which model the loop calls (default: the env/`MODEL` default). That single
    knob is what lets one runner drive a GLM arm and a frontier arm through the *same* loop — the
    machinery is identical; only the model swaps.

    `recover` toggles the S4 **error-recovery** mechanism: when True, a transient tool failure is
    retried at the harness level (up to `max_recoveries` times) inside the same step, WITHOUT
    spending a model turn. `recover=False` is the bare baseline — behaviour is byte-identical to
    S3 (it just dispatches once and feeds any error back). This toggle is the "arm": baseline vs
    +error-recovery, the two configurations the S4 ablation compares (DECISIONS D8/D11 — the
    mechanism wraps the LOOP, never the task; the `Scenario` stays fixed).

    `nudge` toggles the S6 **retry-nudge** mechanism: when True, a non-terminal tool call that fails
    triggers an explicit corrective re-prompt — the harness appends one `user` message that turn
    ("that call failed: …; correct the arguments and call again"). Unlike error-recovery (a harness
    retry, NO model turn), retry-nudge spends a model turn, so it can fix a MALFORMED call a blind
    retry cannot (DECISIONS D19). `nudge=False` is the bare baseline (the raw error is fed back as the
    tool result and the loop moves on). The two toggles are independent arms; either, both, or neither.

    Returns a small summary dict (the oracle's correct/submitted/expected, the model used, and how
    many harness-level recoveries and corrective nudges fired); writes the full trajectory to `out_path`.
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
        "recover": recover, "max_recoveries": max_recoveries, "nudge": nudge,
        "task": scenario.task,
        "ground_truth": scenario.ground_truth,
    })

    stop = "max_steps"        # overwritten once GLM submits or stops talking
    final_answer = None
    submitted = None          # the value GLM passed to submit_answer (None if it never did)
    prompt_tokens = completion_tokens = 0
    total_recoveries = 0      # harness-level retries the error-recovery arm absorbed this run
    total_nudges = 0          # corrective re-prompts the retry-nudge arm issued this run

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
        turn_failures: list[tuple[str, str]] = []  # non-terminal calls that failed this turn
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

            # ACT — dispatch the tool (or record why we couldn't). With error-recovery on, a
            # transient failure is retried HERE, transparently, never spending a model turn.
            if not args_ok:
                ok, result, recoveries = (
                    False, f"malformed JSON arguments: {c.function.arguments!r}", 0)
            else:
                ok, result, recoveries = dispatch_with_recovery(
                    c.function.name, args, scenario.registry,
                    recover=recover, max_recoveries=max_recoveries)
            total_recoveries += recoveries
            log({
                "event": "act", "step": step, "tool_call_id": c.id,
                "tool": c.function.name, "args": args,
                "args_ok": args_ok, "dispatch_ok": ok, "recoveries": recoveries,
            })

            # OBSERVE — feed the outcome (result OR error) back to GLM verbatim.
            log({"event": "observe", "step": step, "tool_call_id": c.id,
                 "ok": ok, "result": result})
            messages.append({"role": "tool", "tool_call_id": c.id, "content": result})
            if not ok:
                turn_failures.append((c.function.name, result))

        # retry-nudge (S6) — after all tool results are threaded back (so the API's tool-call
        # ordering stays valid), append ONE explicit corrective re-prompt this turn if anything
        # failed. It costs the model a turn; the bare baseline (nudge=False) appends nothing.
        if nudge and turn_failures and not terminated:
            messages.append({"role": "user", "content": _nudge_message(turn_failures)})
            total_nudges += 1
            log({"event": "nudge", "step": step, "count": total_nudges,
                 "failures": [{"tool": n, "error": e} for n, e in turn_failures]})

        if terminated:
            break

    # GRADE — the deterministic oracle has the final word (never an LLM).
    correct, detail = grade(submitted, scenario.ground_truth)
    log({"event": "final", "step": step, "stop": stop, "answer": final_answer,
         "recoveries": total_recoveries, "nudges": total_nudges})
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
        "recover": recover,
        "recoveries": total_recoveries,
        "nudge": nudge,
        "nudges": total_nudges,
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
    print(f"recoveries     : {s['recoveries']}  (recover={s['recover']})")
    print(f"nudges         : {s['nudges']}  (nudge={s['nudge']})")
    print(f"submitted      : {s['submitted']!r}   expected: {s['expected']!r}")
    print(f"oracle         : {verdict}")
    print(f"tokens         : prompt={s['tokens']['prompt']} "
          f"completion={s['tokens']['completion']}")
    print(f"trajectory     : {s['trajectory']} ({s['records']} records)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
