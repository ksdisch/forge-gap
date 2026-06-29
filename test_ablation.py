"""test_ablation.py — offline wiring test for the S4 ablation harness.

No network, no model — run with `uv run test_ablation.py`. `run_ablation` itself only orchestrates:
run two arms over the same seeded faults, then hand the k/N counts to the CI functions and write a
summary. We verify that orchestration with a FAKE per-trial driver (so no API calls): both arms run
n trials, the mechanism arm is toggled with recover=True while the baseline stays bare, the counts
flow into Wilson + Newcombe, and the summary lands on disk. The CI *math* itself is pinned
separately in test_stats.py; here we only prove the plumbing.

Exits non-zero if any check fails.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

from ablation import BASELINE_ARM, NUDGE_ARM, RECOVERY_ARM, run_ablation, run_arms

_failures: list[str] = []


def check(label: str, cond: bool) -> None:
    print(f"  [{'ok  ' if cond else 'FAIL'}] {label}")
    if not cond:
        _failures.append(label)


def close(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(a - b) <= tol


def make_fake(base_flags, mech_flags):
    """A stand-in for agent.run. The first len(base_flags) calls are the baseline arm, the next
    len(mech_flags) the mechanism arm; each returns a canned summary. Records the recover flag it
    was called with so we can assert the ablation toggled exactly one arm.
    """
    calls: list[dict] = []
    n = len(base_flags)

    def fake(*, scenario=None, model=None, out_path=None, temperature=None, **kwargs):
        i = len(calls)
        recover = kwargs.get("recover")
        calls.append({"recover": recover, "scenario_name": getattr(scenario, "name", None)})
        correct = base_flags[i] if i < n else mech_flags[i - n]
        return {
            "scenario": getattr(scenario, "name", "fake"), "model": model,
            "stop": "submitted" if correct else "max_steps",
            "correct": correct, "submitted": 158 if correct else None, "expected": 158,
            "recover": bool(recover), "recoveries": 2 if recover else 0,
            "tokens": {"prompt": 1, "completion": 1},
        }

    fake.calls = calls
    return fake


def test_ablation_wiring() -> None:
    print("run_ablation — two arms, paired faults, CIs, summary on disk")
    tmp = tempfile.mkdtemp()
    try:
        base = [True] * 6 + [False] * 4   # baseline 6/10
        mech = [True] * 9 + [False] * 1   # mechanism 9/10
        fake = make_fake(base, mech)
        s = run_ablation("z-ai/glm-4.6", 10, 0.6, run_fn=fake, runs_dir=tmp, verbose=False)

        check("ran 2n trials total (baseline then mechanism)", len(fake.calls) == 20)
        check("baseline correct == 6", s["baseline"]["correct"] == 6)
        check("mechanism correct == 9", s["mechanism"]["correct"] == 9)
        check("delta == 0.30", close(s["gap_closure"]["delta"], 0.3))

        check("baseline arm ran bare (recover not True)",
              all(c["recover"] in (False, None) for c in fake.calls[:10]))
        check("mechanism arm ran with recover=True",
              all(c["recover"] is True for c in fake.calls[10:]))
        check("mechanism recoveries aggregated (2 x 10)", s["mechanism"]["recoveries"] == 20)
        check("baseline recoveries == 0", s["baseline"]["recoveries"] == 0)

        check("both arms saw faulted scenarios (same per-index seed source)",
              all(c["scenario_name"] == "order_grand_total__faults0.6" for c in fake.calls))

        check("baseline carries a 2-point Wilson CI", len(s["baseline"]["wilson"]) == 2)
        check("mechanism carries a 2-point Wilson CI", len(s["mechanism"]["wilson"]) == 2)
        check("gap_closure carries a 2-point Newcombe CI", len(s["gap_closure"]["newcombe"]) == 2)
        check("excludes_zero is a bool", isinstance(s["gap_closure"]["excludes_zero"], bool))

        check("summary.json written", os.path.exists(s["summary_path"]))
        reloaded = json.loads(open(s["summary_path"], encoding="utf-8").read())
        check("summary.json round-trips", reloaded["gap_closure"]["delta"] == s["gap_closure"]["delta"])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def make_fake_multi(arm_flags):
    """A stand-in for agent.run across N arms. arm_flags is one correctness list per arm (each length
    n); calls 0..n-1 are arm 0, n..2n-1 arm 1, and so on. Records the recover/nudge flags each call
    was driven with, so we can assert exactly one mechanism toggled per arm.
    """
    calls: list[dict] = []
    n = len(arm_flags[0])

    def fake(*, scenario=None, model=None, out_path=None, temperature=None, **kwargs):
        idx = len(calls)
        arm, within = divmod(idx, n)
        recover, nudge = kwargs.get("recover"), kwargs.get("nudge")
        calls.append({"recover": recover, "nudge": nudge, "arm": arm})
        correct = arm_flags[arm][within]
        return {
            "scenario": getattr(scenario, "name", "fake"), "model": model,
            "stop": "submitted" if correct else "max_steps",
            "correct": correct, "submitted": 158 if correct else None, "expected": 158,
            "recover": bool(recover), "recoveries": 2 if recover else 0,
            "nudge": bool(nudge), "nudges": 3 if nudge else 0,
            "tokens": {"prompt": 1, "completion": 1},
        }

    fake.calls = calls
    return fake


def test_run_arms_three_arms() -> None:
    print("run_arms — three arms over shared faults; per-arm Wilson + Newcombe vs baseline")
    tmp = tempfile.mkdtemp()
    try:
        base = [True] * 5 + [False] * 5   # baseline 5/10
        rec = [True] * 5 + [False] * 5    # +error-recovery 5/10  (≈ baseline — wrong guardrail, null)
        nud = [True] * 9 + [False] * 1    # +retry-nudge 9/10      (the matched guardrail lifts)
        fake = make_fake_multi([base, rec, nud])
        s = run_arms("z-ai/glm-4.6", 10, 0.6, arms=[BASELINE_ARM, RECOVERY_ARM, NUDGE_ARM],
                     fault_kind="malformed", run_fn=fake, runs_dir=tmp, out_name="m.json",
                     verbose=False)

        check("ran 3 arms x n trials", len(fake.calls) == 30)
        check("summary carries 3 arms", len(s["arms"]) == 3)
        check("fault_kind passed through", s["fault_kind"] == "malformed")
        check("arm order preserved (baseline first)",
              [a["label"] for a in s["arms"]] == ["baseline", "error_recovery", "retry_nudge"])

        check("baseline has NO gap_vs_baseline", "gap_vs_baseline" not in s["arms"][0])
        check("recovery arm carries a gap_vs_baseline", "gap_vs_baseline" in s["arms"][1])
        check("nudge arm carries a gap_vs_baseline", "gap_vs_baseline" in s["arms"][2])

        check("recovery delta == 0.0 (the wrong guardrail does nothing)",
              close(s["arms"][1]["gap_vs_baseline"]["delta"], 0.0))
        check("recovery gap straddles 0 -> null verdict",
              s["arms"][1]["gap_vs_baseline"]["excludes_zero"] is False)
        check("nudge delta == 0.40", close(s["arms"][2]["gap_vs_baseline"]["delta"], 0.4))
        check("nudge excludes_zero is a bool", isinstance(s["arms"][2]["gap_vs_baseline"]["excludes_zero"], bool))

        check("recoveries aggregated on the recovery arm (2 x 10)", s["arms"][1]["recoveries"] == 20)
        check("nudges aggregated on the nudge arm (3 x 10)", s["arms"][2]["nudges"] == 30)
        check("baseline arm ran bare (no recover, no nudge)",
              all(c["recover"] in (False, None) and c["nudge"] in (False, None) for c in fake.calls[:10]))
        check("recovery arm drove recover=True only", all(c["recover"] is True for c in fake.calls[10:20]))
        check("nudge arm drove nudge=True only", all(c["nudge"] is True for c in fake.calls[20:30]))

        check("summary written to out_name", os.path.exists(s["summary_path"]) and s["summary_path"].endswith("m.json"))
        reloaded = json.loads(open(s["summary_path"], encoding="utf-8").read())
        check("summary round-trips", reloaded["arms"][2]["gap_vs_baseline"]["delta"] == s["arms"][2]["gap_vs_baseline"]["delta"])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    print("Offline tests: the S4 ablation harness\n" + "-" * 38)
    test_ablation_wiring()
    print()
    test_run_arms_three_arms()
    print("\n" + "-" * 38)
    if _failures:
        print(f"{len(_failures)} check(s) FAILED:")
        for f in _failures:
            print(f"  - {f}")
        return 1
    print("All checks passed — the ablation runs both arms, pairs faults, and computes CIs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
