"""test_runner.py — offline unit tests for the S3 N-trial runner.

No network, no model, no pytest — runnable with `uv run test_runner.py` (same hand-rolled
style as test_oracle.py). The runner's *only* job is bookkeeping: drive one model arm N
times, count how many runs the oracle marked correct, and lay the results on disk. That
bookkeeping is exactly what must be right BEFORE we spend a single API call — if the k/N
counting is off, every completion-rate number downstream is wrong.

We test it by injecting a FAKE `run_fn` in place of the real `agent.run` (which would hit the
network). The fake returns canned summary dicts, so we can assert run_arm aggregates them
correctly, threads the model through, gives each trial a distinct trajectory path, and writes
a results.jsonl — all offline, deterministically.

Exits non-zero if any check fails.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

from runner import run_arm

_failures: list[str] = []


def check(label: str, cond: bool) -> None:
    print(f"  [{'ok  ' if cond else 'FAIL'}] {label}")
    if not cond:
        _failures.append(label)


def make_fake(correct_flags, stops=None):
    """Build a stand-in for agent.run that returns canned results and records its calls.

    `correct_flags[i]` is what the oracle "decided" for trial i; `stops[i]` (optional) is the
    stop reason. The fake records every call's keyword args so we can assert the runner threaded
    the right model and a distinct out_path into each trial.
    """
    calls: list[dict] = []

    def fake(*, scenario=None, model=None, out_path=None, temperature=None):
        i = len(calls)
        calls.append({"scenario": scenario, "model": model,
                      "out_path": out_path, "temperature": temperature})
        correct = correct_flags[i]
        stop = stops[i] if stops else ("submitted" if correct else "no_submit")
        return {
            "scenario": getattr(scenario, "name", "fake"),
            "model": model,
            "stop": stop,
            "correct": correct,
            "submitted": 158 if correct else None,
            "expected": 158,
            "final_answer": 158 if correct else None,
            "trajectory": out_path,
        }

    fake.calls = calls
    return fake


def test_aggregation() -> None:
    print("run_arm — k/N aggregation + per-trial bookkeeping")
    tmp = tempfile.mkdtemp()
    try:
        flags = [True, False, True, True, False]  # 3 correct out of 5
        fake = make_fake(flags)
        arm = run_arm("glm", "z-ai/glm-4.6", 5, run_fn=fake, runs_dir=tmp, verbose=False)

        check("ran exactly n trials", len(fake.calls) == 5)
        check("correct count == 3", arm["correct"] == 3)
        check("n == 5", arm["n"] == 5)
        check("rate == 0.6", abs(arm["rate"] - 0.6) < 1e-9)
        check("label echoed", arm["label"] == "glm")
        check("model echoed", arm["model"] == "z-ai/glm-4.6")
        check("model threaded into every call",
              all(c["model"] == "z-ai/glm-4.6" for c in fake.calls))

        paths = [c["out_path"] for c in fake.calls]
        check("every trial got a distinct out_path", len(set(paths)) == 5)
        check("first trial path is trial-00.jsonl", paths[0].endswith("trial-00.jsonl"))
        check("trial paths live under the arm dir",
              all(os.path.join("glm", "") in p or f"{os.sep}glm{os.sep}" in p for p in paths))

        rp = arm["results_path"]
        check("results.jsonl exists", os.path.exists(rp))
        lines = open(rp, encoding="utf-8").read().splitlines()
        check("results.jsonl has one line per trial", len(lines) == 5)
        first = json.loads(lines[0])
        check("results line is a real summary dict", first.get("correct") is True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_stop_tally_and_edges() -> None:
    print("run_arm — stop-reason tally + all-correct edge")
    tmp = tempfile.mkdtemp()
    try:
        # mixed stop reasons: 1 correct submit, 1 wrong submit, 1 no_submit, 1 max_steps
        flags = [True, False, False, False]
        stops = ["submitted", "submitted", "no_submit", "max_steps"]
        fake = make_fake(flags, stops=stops)
        arm = run_arm("mix", "m", 4, run_fn=fake, runs_dir=tmp, verbose=False)
        check("correct == 1", arm["correct"] == 1)
        check("by_stop sums to n", sum(arm["by_stop"].values()) == 4)
        check("by_stop counts submitted twice", arm["by_stop"].get("submitted") == 2)
        check("by_stop counts no_submit once", arm["by_stop"].get("no_submit") == 1)
        check("by_stop counts max_steps once", arm["by_stop"].get("max_steps") == 1)

        all_ok = make_fake([True, True])
        arm2 = run_arm("perfect", "m", 2, run_fn=all_ok, runs_dir=tmp, verbose=False)
        check("all correct -> rate 1.0", arm2["rate"] == 1.0)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_make_scenario() -> None:
    print("run_arm — make_scenario builds a fresh scenario per trial")
    tmp = tempfile.mkdtemp()
    try:
        seen = []

        def fake(*, scenario, model, out_path, temperature):
            seen.append(scenario)
            return {"correct": True, "stop": "submitted", "submitted": 158}

        def make_scenario(i):
            return f"scenario-{i}"

        run_arm("mk", "m", 3, make_scenario=make_scenario,
                run_fn=fake, runs_dir=tmp, verbose=False)
        check("make_scenario called once per trial, in order",
              seen == ["scenario-0", "scenario-1", "scenario-2"])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_run_kwargs_passthrough() -> None:
    """run_kwargs reach run_fn verbatim (the S4 seam for toggling a mechanism on one arm)."""
    print("run_arm — run_kwargs forwarded to the per-trial driver")
    tmp = tempfile.mkdtemp()
    try:
        seen = []

        def fake(*, scenario=None, model=None, out_path=None, temperature=None, **kwargs):
            seen.append(kwargs)
            return {"correct": True, "stop": "submitted", "submitted": 158, "recoveries": kwargs.get("recover") and 3 or 0}

        arm = run_arm("mech", "m", 2, run_fn=fake, run_kwargs={"recover": True},
                      runs_dir=tmp, verbose=False)
        check("recover=True forwarded to every trial", all(k.get("recover") is True for k in seen))
        check("recoveries aggregated from summaries", arm["recoveries"] == 6)

        # default: no run_kwargs -> driver called with no extras (S3 behaviour unchanged)
        seen.clear()
        run_arm("bare", "m", 2, run_fn=fake, runs_dir=tmp, verbose=False)
        check("no run_kwargs -> no extra kwargs passed", all(k == {} for k in seen))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    print("Offline tests: the S3 N-trial runner\n" + "-" * 44)
    test_aggregation()
    print()
    test_stop_tally_and_edges()
    print()
    test_make_scenario()
    print()
    test_run_kwargs_passthrough()
    print("\n" + "-" * 44)
    if _failures:
        print(f"{len(_failures)} check(s) FAILED:")
        for f in _failures:
            print(f"  - {f}")
        return 1
    print("All checks passed — the runner counts k/N, threads the model, and lays out results.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
