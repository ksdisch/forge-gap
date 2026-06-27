"""test_recover.py — offline tests for the S4 error-recovery mechanism.

No network, no real model — run with `uv run test_recover.py`. Two layers:

  1. The pure heart: `_is_retryable` + `dispatch_with_recovery`. A registry whose tool fails a
     fixed number of times then succeeds is a deterministic fixture, so we can pin exactly when
     the harness retries, how many recoveries it spends, and that it leaves permanent errors alone.
  2. End-to-end wiring: drive the real `agent.run` loop with a FAKE chat (canned tool calls) over a
     scenario whose lookup fails transiently, and confirm the loop threads `recover`, counts the
     recoveries, and logs them — while the bare baseline (recover=False) absorbs nothing.

Exits non-zero if any check fails.
"""
from __future__ import annotations

import json
import sys
import tempfile
from dataclasses import replace
from types import SimpleNamespace

import agent
from agent import _is_retryable, dispatch_with_recovery, run as agent_run
from faults import ToolUnavailable
from scenario import ORDER_SCENARIO, ORDERS, get_ship_rate

_failures: list[str] = []


def check(label: str, cond: bool) -> None:
    print(f"  [{'ok  ' if cond else 'FAIL'}] {label}")
    if not cond:
        _failures.append(label)


# --- fixtures -------------------------------------------------------------
def transient_order_tool(fail_times: int):
    """A get_order that raises a transient 503 its first `fail_times` calls, then succeeds."""
    state = {"n": 0}

    def get_order(order_id: str) -> str:
        if state["n"] < fail_times:
            state["n"] += 1
            raise ToolUnavailable(f"503 get_order temporarily unavailable, retry")
        return json.dumps(ORDERS[order_id])

    return get_order


def scenario_with_transient_order(fail_times: int):
    """ORDER_SCENARIO but with a get_order that 503s `fail_times` times before succeeding."""
    reg = {"get_order": transient_order_tool(fail_times), "get_ship_rate": get_ship_rate}
    return replace(ORDER_SCENARIO, registry=reg)


def make_fake_chat(script):
    """Stand-in for glm.chat: yields canned turns. Each turn is a list of (name, args_dict) tool
    calls, or None for a content-only reply. Ignores the conversation — the faults live in the
    tools, so a canned script is enough to exercise the loop's act/recover path deterministically.
    """
    turns = list(script)
    state = {"i": 0}

    def fake_chat(messages, **kwargs):
        i = state["i"]
        state["i"] += 1
        turn = turns[i] if i < len(turns) else None
        if turn is None:
            msg = SimpleNamespace(content="done", tool_calls=None)
            finish = "stop"
        else:
            calls = [
                SimpleNamespace(id=f"call_{i}_{j}",
                                function=SimpleNamespace(name=name, arguments=json.dumps(args)))
                for j, (name, args) in enumerate(turn)
            ]
            msg = SimpleNamespace(content=None, tool_calls=calls)
            finish = "tool_calls"
        choice = SimpleNamespace(message=msg, finish_reason=finish)
        usage = SimpleNamespace(prompt_tokens=1, completion_tokens=1)
        return SimpleNamespace(choices=[choice], usage=usage)

    return fake_chat


# --- 1. the pure heart ----------------------------------------------------
def test_is_retryable() -> None:
    print("_is_retryable — transient signals vs permanent errors")
    for s in ["503 get_order temporarily unavailable, retry",
              "ToolUnavailable: 503 ...", "Read timed out", "429 rate limit"]:
        check(f"retryable: {s[:32]!r}", _is_retryable(s) is True)
    for s in ["KeyError: \"no order 'ORD-999'\"",
              "malformed JSON arguments: '{bad'", "unknown tool: 'frobnicate'"]:
        check(f"permanent: {s[:32]!r}", _is_retryable(s) is False)


def test_dispatch_with_recovery() -> None:
    print("dispatch_with_recovery — retries transient failures, leaves permanent ones")
    # transient: fails twice then succeeds
    reg = {"get_order": transient_order_tool(2)}
    ok, res, rec = dispatch_with_recovery("get_order", {"order_id": "ORD-204"}, reg,
                                          recover=True, max_recoveries=3)
    check("recovers after 2 transient failures -> ok", ok is True)
    check("spent exactly 2 recoveries", rec == 2)
    check("returns the real record", "Acme" in res)

    # baseline (recover=False) never retries
    reg2 = {"get_order": transient_order_tool(2)}
    ok, res, rec = dispatch_with_recovery("get_order", {"order_id": "ORD-204"}, reg2,
                                          recover=False, max_recoveries=3)
    check("recover=False -> dispatches once, fails", ok is False)
    check("recover=False -> 0 recoveries", rec == 0)
    check("recover=False -> error is the 503", "503" in res or "ToolUnavailable" in res)

    # budget exhausted: needs 2 but only allowed 1
    reg3 = {"get_order": transient_order_tool(2)}
    ok, res, rec = dispatch_with_recovery("get_order", {"order_id": "ORD-204"}, reg3,
                                          recover=True, max_recoveries=1)
    check("exhausting max_recoveries -> still fails", ok is False)
    check("exhausting max_recoveries -> spent the cap (1)", rec == 1)

    # permanent error is NOT retried even with recover on
    def bad_order(order_id):
        raise KeyError(f"no order {order_id!r}")

    ok, res, rec = dispatch_with_recovery("get_order", {"order_id": "ORD-999"},
                                          {"get_order": bad_order},
                                          recover=True, max_recoveries=3)
    check("permanent KeyError not retried -> 0 recoveries", rec == 0)
    check("permanent error still reported as failure", ok is False)

    # success on the first try spends nothing
    ok, res, rec = dispatch_with_recovery("get_order", {"order_id": "ORD-204"},
                                          {"get_order": transient_order_tool(0)},
                                          recover=True, max_recoveries=3)
    check("clean call -> 0 recoveries", rec == 0 and ok is True)


# --- 2. end-to-end wiring through agent.run -------------------------------
def _run_once(recover: bool, fail_times: int) -> dict:
    """Drive agent.run over a transient-order scenario with a canned chat; return (summary, traj)."""
    script = [
        [("get_order", {"order_id": "ORD-204"})],
        [("get_ship_rate", {"zone": "WEST"})],
        [("submit_answer", {"value": 158})],
    ]
    saved = agent.chat
    agent.chat = make_fake_chat(script)
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as fh:
            out_path = fh.name
        summary = agent_run(scenario=scenario_with_transient_order(fail_times),
                            recover=recover, max_recoveries=3, out_path=out_path)
        traj = [json.loads(line) for line in open(out_path, encoding="utf-8")]
        return summary, traj
    finally:
        agent.chat = saved


def test_run_end_to_end() -> None:
    print("agent.run — error-recovery rescues a transient lookup; baseline absorbs nothing")
    summary, traj = _run_once(recover=True, fail_times=2)
    check("recover=True completes correctly", summary["correct"] is True)
    check("recover=True records 2 harness recoveries", summary["recoveries"] == 2)
    check("summary echoes recover=True", summary["recover"] is True)
    order_act = next(r for r in traj if r["event"] == "act" and r["tool"] == "get_order")
    check("recovered get_order observation is OK (dispatch_ok)", order_act["dispatch_ok"] is True)
    check("recovered get_order act logs recoveries=2", order_act["recoveries"] == 2)

    summary, traj = _run_once(recover=False, fail_times=2)
    check("baseline records 0 recoveries", summary["recoveries"] == 0)
    check("summary echoes recover=False", summary["recover"] is False)
    order_act = next(r for r in traj if r["event"] == "act" and r["tool"] == "get_order")
    check("baseline get_order failed (dispatch_ok False)", order_act["dispatch_ok"] is False)
    check("baseline get_order act logs recoveries=0", order_act["recoveries"] == 0)


def main() -> int:
    print("Offline tests: the S4 error-recovery mechanism\n" + "-" * 46)
    for t in (test_is_retryable, test_dispatch_with_recovery, test_run_end_to_end):
        t()
        print()
    print("-" * 46)
    if _failures:
        print(f"{len(_failures)} check(s) FAILED:")
        for f in _failures:
            print(f"  - {f}")
        return 1
    print("All checks passed — recovery retries only transient failures, without spending a turn.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
