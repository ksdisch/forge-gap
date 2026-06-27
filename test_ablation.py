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

from ablation import run_ablation

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


def main() -> int:
    print("Offline tests: the S4 ablation harness\n" + "-" * 38)
    test_ablation_wiring()
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
