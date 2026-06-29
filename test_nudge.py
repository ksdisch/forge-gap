"""test_nudge.py — offline tests for the S6 retry-nudge mechanism.

No network, no real model — run with `uv run test_nudge.py`. Two layers:

  1. The pure heart: `_nudge_message` builds an explicit corrective re-prompt naming the failed tool
     and its error, telling the model to fix-and-retry (not blindly repeat).
  2. End-to-end wiring: drive the real `agent.run` loop with a FAKE chat (canned tool calls) over a
     malformed-fault scenario. We snapshot the messages handed to `chat` each turn to PROVE the
     nudge actually reaches the model after a failed call, that it's counted, and that the bare
     baseline (nudge=False) appends nothing. Contrast with error-recovery: retry-nudge spends a model
     turn (a re-prompt), so the count is "corrective re-prompts issued," not harness retries.

Exits non-zero if any check fails.
"""
from __future__ import annotations

import json
import sys
import tempfile
from types import SimpleNamespace

import agent
from agent import _nudge_message, run as agent_run
from faults import with_malformed_faults
from scenario import ORDER_SCENARIO

_failures: list[str] = []


def check(label: str, cond: bool) -> None:
    print(f"  [{'ok  ' if cond else 'FAIL'}] {label}")
    if not cond:
        _failures.append(label)


def make_capturing_chat(script):
    """Stand-in for glm.chat: plays a canned script AND snapshots the messages it is handed each
    call (so a test can prove what the model actually saw). Each script turn is a list of
    (name, args_dict) tool calls, or None for a content-only reply.
    """
    turns = list(script)
    state = {"i": 0}
    snapshots: list[list[dict]] = []

    def fake_chat(messages, **kwargs):
        snapshots.append(list(messages))  # point-in-time view (loop appends, never mutates in place)
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

    fake_chat.snapshots = snapshots
    return fake_chat


def _run(script, *, nudge: bool, seed: int = 1):
    """Drive agent.run over a fully-armed malformed scenario with a canned, capturing chat."""
    scen = with_malformed_faults(ORDER_SCENARIO, rate=1.0, seed=seed)  # both tools armed
    fake = make_capturing_chat(script)
    saved = agent.chat
    agent.chat = fake
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as fh:
            out_path = fh.name
        summary = agent_run(scenario=scen, nudge=nudge, out_path=out_path)
        traj = [json.loads(line) for line in open(out_path, encoding="utf-8")]
        return summary, traj, fake.snapshots
    finally:
        agent.chat = saved


# The model "reads the hint and corrects" — uncorrected call fails, then the aliased param succeeds.
CORRECTING_SCRIPT = [
    [("get_order", {"order_id": "ORD-204"})],   # armed -> MalformedCall (fails) -> nudge
    [("get_order", {"id": "ORD-204"})],         # corrected -> succeeds
    [("get_ship_rate", {"zone": "WEST"})],      # armed -> MalformedCall (fails) -> nudge
    [("get_ship_rate", {"region": "WEST"})],    # corrected -> succeeds
    [("submit_answer", {"value": 158})],        # done
]

# The model "stubbornly repeats" the documented param every time — never corrects.
REPEATING_SCRIPT = [[("get_order", {"order_id": "ORD-204"})] for _ in range(6)]


def test_nudge_message() -> None:
    print("_nudge_message — explicit, corrective, names the tool + error")
    msg = _nudge_message([("get_order", "MalformedCall: 400 invalid_argument: use 'id' instead")])
    check("mentions the failed tool", "get_order" in msg)
    check("surfaces the error text", "invalid_argument" in msg)
    check("tells the model to correct (not blindly repeat)",
          "correct" in msg.lower() and "repeat" in msg.lower())


def test_nudge_reaches_model_and_counts() -> None:
    print("agent.run nudge=True — the re-prompt reaches the model, is counted, completes")
    summary, traj, snaps = _run(CORRECTING_SCRIPT, nudge=True)
    check("completes correctly once corrected", summary["correct"] is True)
    check("summary echoes nudge=True", summary["nudge"] is True)
    check("counts 2 nudges (one per failed turn)", summary["nudges"] == 2)

    nudge_events = [r for r in traj if r["event"] == "nudge"]
    check("logs a nudge event per failed turn", len(nudge_events) == 2)

    # The decisive wiring proof: on the turn AFTER the first failure, the model is handed a user
    # message carrying the nudge (so a real GLM would see it).
    after_first_failure = snaps[1]
    nudge_msgs = [m for m in after_first_failure
                  if m.get("role") == "user" and "correct" in str(m.get("content", "")).lower()
                  and "get_order" in str(m.get("content", ""))]
    check("model actually SEES the nudge next turn (user re-prompt present)", len(nudge_msgs) == 1)


def test_baseline_appends_nothing() -> None:
    print("agent.run nudge=False — bare baseline appends no nudge")
    summary, traj, snaps = _run(CORRECTING_SCRIPT, nudge=False)
    check("summary echoes nudge=False", summary["nudge"] is False)
    check("counts 0 nudges", summary["nudges"] == 0)
    check("logs no nudge events", not any(r["event"] == "nudge" for r in traj))
    # No injected user re-prompt anywhere after the opening task message.
    injected = [m for snap in snaps for m in snap
                if m.get("role") == "user" and "correct the arguments" in str(m.get("content", "")).lower()]
    check("no corrective user message ever injected", injected == [])


def test_uncorrected_model_still_fails() -> None:
    print("malformed fault holds — a model that never corrects does not complete (nudge off)")
    summary, _traj, _snaps = _run(REPEATING_SCRIPT, nudge=False)
    check("stubborn repeats never complete (max_steps)", summary["correct"] is False)
    check("baseline spent 0 nudges", summary["nudges"] == 0)


def main() -> int:
    print("Offline tests: the S6 retry-nudge mechanism\n" + "-" * 43)
    for t in (test_nudge_message, test_nudge_reaches_model_and_counts,
              test_baseline_appends_nothing, test_uncorrected_model_still_fails):
        t()
        print()
    print("-" * 43)
    if _failures:
        print(f"{len(_failures)} check(s) FAILED:")
        for f in _failures:
            print(f"  - {f}")
        return 1
    print("All checks passed — retry-nudge re-prompts the model on a failed call, counted, "
          "and off by default.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
