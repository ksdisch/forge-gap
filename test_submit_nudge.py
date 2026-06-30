"""test_submit_nudge.py — offline tests for the S8 submit-nudge mechanism.

No network, no real model — run with `uv run test_submit_nudge.py`. Two layers:

  1. The pure heart: `_submit_nudge_message` builds a corrective re-prompt telling a model that
     stopped WITHOUT submitting to actually call the terminal `submit_answer` tool now.
  2. End-to-end wiring: drive the real `agent.run` loop with a FAKE chat (canned turns) over the
     CLEAN scenario. We snapshot the messages handed to `chat` each turn to PROVE the submit-nudge
     reaches the model after a no-call turn, that it's counted, and that the bare baseline
     (submit_nudge=False) appends nothing and ends as `no_submit`.

This is the natural-failure counterpart to retry-nudge: retry-nudge fires on a *failed* call;
submit-nudge fires when the model ends a turn in prose with no submission at all (mistral-nemo's
"the total is 158 — calling submit_answer…" then stops).

Exits non-zero if any check fails.
"""
from __future__ import annotations

import json
import sys
import tempfile
from types import SimpleNamespace

import agent
from agent import _submit_nudge_message
from agent import run as agent_run
from scenario import ORDER_SCENARIO

_failures: list[str] = []


def check(label: str, cond: bool) -> None:
    print(f"  [{'ok  ' if cond else 'FAIL'}] {label}")
    if not cond:
        _failures.append(label)


def make_capturing_chat(script):
    """Stand-in for glm.chat: plays a canned script AND snapshots the messages it is handed each
    call. Each script turn is a list of (name, args_dict) tool calls, or None for a prose-only reply
    — the no-submit turn that submit-nudge targets."""
    turns = list(script)
    state = {"i": 0}
    snapshots: list[list[dict]] = []

    def fake_chat(messages, **kwargs):
        snapshots.append(list(messages))  # point-in-time view (loop appends, never mutates in place)
        i = state["i"]
        state["i"] += 1
        turn = turns[i] if i < len(turns) else None
        if turn is None:
            # A prose-only reply: the model says it will submit but emits no tool call.
            msg = SimpleNamespace(
                content="The grand total is 140 + 18 = 158. Calling submit_answer with 158.",
                tool_calls=None)
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

    fake_chat.snapshots = snapshots
    return fake_chat


def _run(script, *, submit_nudge: bool):
    """Drive agent.run over the CLEAN scenario with a canned, capturing chat."""
    fake = make_capturing_chat(script)
    saved = agent.chat
    agent.chat = fake
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as fh:
            out_path = fh.name
        summary = agent_run(scenario=ORDER_SCENARIO, submit_nudge=submit_nudge, out_path=out_path)
        traj = [json.loads(line) for line in open(out_path, encoding="utf-8")]
        return summary, traj, fake.snapshots
    finally:
        agent.chat = saved


# The model does both lookups, then STALLS in prose (no submit), then submits after the nudge.
STALL_THEN_SUBMIT_SCRIPT = [
    [("get_order", {"order_id": "ORD-204"})],   # turn 0 -> ok
    [("get_ship_rate", {"zone": "WEST"})],      # turn 1 -> ok
    None,                                        # turn 2 -> prose, no call -> submit-nudge fires
    [("submit_answer", {"value": 158})],        # turn 3 -> submits after the nudge
]

# The model submits straight away — submit-nudge must NOT fire (nothing to prod).
CLEAN_SUBMIT_SCRIPT = [
    [("get_order", {"order_id": "ORD-204"})],
    [("get_ship_rate", {"zone": "WEST"})],
    [("submit_answer", {"value": 158})],
]


def test_submit_nudge_message() -> None:
    print("_submit_nudge_message — tells a stalled model to call the terminal tool")
    msg = _submit_nudge_message()
    check("names the terminal tool", "submit_answer" in msg)
    check("tells the model to actually call/submit it",
          "call" in msg.lower() or "submit" in msg.lower())


def test_submit_nudge_reaches_model_and_counts() -> None:
    print("agent.run submit_nudge=True — the re-prompt reaches the model, is counted, completes")
    summary, traj, snaps = _run(STALL_THEN_SUBMIT_SCRIPT, submit_nudge=True)
    check("completes once prodded to submit", summary["correct"] is True)
    check("summary echoes submit_nudge=True", summary["submit_nudge"] is True)
    check("counts 1 submit-nudge (one stalled turn)", summary["submit_nudges"] == 1)
    check("final stop is 'submitted', not 'no_submit'", summary["stop"] == "submitted")

    events = [r for r in traj if r["event"] == "submit_nudge"]
    check("logs a submit_nudge event for the stalled turn", len(events) == 1)

    # Wiring proof: the turn AFTER the stall, the model is handed a user re-prompt naming submit_answer.
    after_stall = snaps[3]
    prods = [m for m in after_stall
             if m.get("role") == "user" and "submit_answer" in str(m.get("content", ""))]
    check("model actually SEES the submit-nudge next turn", len(prods) == 1)


def test_baseline_ends_no_submit() -> None:
    print("agent.run submit_nudge=False — bare baseline never prods, ends no_submit")
    summary, traj, snaps = _run(STALL_THEN_SUBMIT_SCRIPT, submit_nudge=False)
    check("summary echoes submit_nudge=False", summary["submit_nudge"] is False)
    check("counts 0 submit-nudges", summary["submit_nudges"] == 0)
    check("ends as no_submit (stalled prose is terminal)", summary["stop"] == "no_submit")
    check("does not complete", summary["correct"] is False)
    check("logs no submit_nudge events", not any(r["event"] == "submit_nudge" for r in traj))
    injected = [m for snap in snaps for m in snap
                if m.get("role") == "user" and "submit_answer" in str(m.get("content", ""))
                and "haven't" in str(m.get("content", "")).lower()]
    check("no corrective user message ever injected", injected == [])


def test_no_nudge_when_model_submits() -> None:
    print("agent.run submit_nudge=True — a model that submits on its own is never prodded")
    summary, _traj, _snaps = _run(CLEAN_SUBMIT_SCRIPT, submit_nudge=True)
    check("completes", summary["correct"] is True)
    check("fires 0 submit-nudges (nothing to prod)", summary["submit_nudges"] == 0)


def main() -> int:
    print("Offline tests: the S8 submit-nudge mechanism\n" + "-" * 44)
    for t in (test_submit_nudge_message, test_submit_nudge_reaches_model_and_counts,
              test_baseline_ends_no_submit, test_no_nudge_when_model_submits):
        t()
        print()
    print("-" * 44)
    if _failures:
        print(f"{len(_failures)} check(s) FAILED:")
        for f in _failures:
            print(f"  - {f}")
        return 1
    print("All checks passed — submit-nudge re-prompts a stalled model to call the terminal tool, "
          "counted, and off by default.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
