"""runner.py — the S3 N-trial runner (the "does a gap even exist?" diagnostic).

S2 grades ONE run PASS/FAIL. But a single run is one coin flip — GLM is stochastic (a bit
random), so one PASS tells you almost nothing about the *rate*. S3 turns one run into a rate:
run the same scenario N times for one model and report how often it completes.

The unit here is an **arm** — one configuration under test. In S3 an arm is just a model
(GLM-4.6, then a frontier model). Later (S4+) "+retry-nudge" vs "baseline" become arms too,
which is why the runner is parameterised by model now and will grow mechanism toggles then —
NOT before (see DECISIONS D11: this is the lean diagnostic, not the S4 ablation harness).

What it does, and nothing more:
  - loop the bare agent N times for one (label, model),
  - write each trial's full trajectory to runs/<label>/trial-NN.jsonl (so failures can be
    hand-read — the input to the mechanical-vs-cognitive triage),
  - collect the per-trial summaries into runs/<label>/results.jsonl,
  - report the raw completion rate k/N and a tally of how runs ended (by_stop).

Deliberately ABSENT (they arrive later, on purpose):
  - confidence intervals (Wilson/Newcombe) — S4/S5; here we just eyeball the gap,
  - any reliability mechanism — S5+; the whole point is to measure the bare baseline first.

Run (GLM-first, per DECISIONS D10):
    uv run runner.py                                  # GLM-4.6 baseline @ N=20 — read this FIRST
    uv run runner.py frontier <model-slug> 20         # the frontier arm, once GLM is read
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter

from agent import TEMPERATURE
from agent import run as agent_run
from faults import with_faults
from scenario import ORDER_SCENARIO, Scenario

DEFAULT_N = 20


def run_arm(
    label: str,
    model: str,
    n: int,
    *,
    scenario: Scenario = ORDER_SCENARIO,
    make_scenario=None,
    run_fn=agent_run,
    runs_dir: str = "runs",
    temperature: float = TEMPERATURE,
    verbose: bool = True,
) -> dict:
    """Run `scenario` `n` times on one model `arm`; return its completion rate + bookkeeping.

    ZERO mechanisms: this only loops the bare agent and tallies what the deterministic oracle
    already decided per run. `make_scenario(i)`, if given, builds a fresh scenario per trial i
    (used to inject per-trial seeded faults — DECISIONS D12); otherwise the fixed `scenario` is
    used every trial. `run_fn` is the per-trial driver (defaults to the real `agent.run`; tests
    inject a fake so the k/N counting can be verified without any API calls).
    """
    arm_dir = os.path.join(runs_dir, label)
    os.makedirs(arm_dir, exist_ok=True)

    if verbose:
        print(f"[{label}] model={model}  n={n}  temp={temperature}")

    trials: list[dict] = []
    for i in range(n):
        scen = make_scenario(i) if make_scenario is not None else scenario
        out_path = os.path.join(arm_dir, f"trial-{i:02d}.jsonl")
        summary = run_fn(scenario=scen, model=model,
                         out_path=out_path, temperature=temperature)
        trials.append(summary)
        if verbose:
            mark = "ok  " if summary["correct"] else "MISS"
            print(f"  trial {i:02d}/{n}  [{mark}] stop={summary['stop']:<10} "
                  f"submitted={summary.get('submitted')!r}")

    correct = sum(1 for t in trials if t["correct"])
    rate = correct / n if n else 0.0
    by_stop = dict(Counter(t["stop"] for t in trials))
    tok_prompt = sum((t.get("tokens") or {}).get("prompt", 0) for t in trials)
    tok_completion = sum((t.get("tokens") or {}).get("completion", 0) for t in trials)

    results_path = os.path.join(arm_dir, "results.jsonl")
    with open(results_path, "w", encoding="utf-8") as f:
        for t in trials:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")

    if verbose:
        print(f"[{label}] completion rate: {correct}/{n} = {rate:.1%}   by_stop={by_stop}")
        print(f"[{label}] tokens: prompt={tok_prompt} completion={tok_completion}   "
              f"results -> {results_path}")

    return {
        "label": label,
        "model": model,
        "n": n,
        "correct": correct,
        "rate": rate,
        "by_stop": by_stop,
        "tokens": {"prompt": tok_prompt, "completion": tok_completion},
        "results_path": results_path,
        "trials": trials,
    }


def main(argv: list[str]) -> int:
    """`uv run runner.py [label] [model] [n] [fault_rate]` — defaults to GLM-4.6 baseline @ N=20.

    Per DECISIONS D10 (GLM-first): run the GLM baseline first and READ it before spending the
    frontier arm. Pass a `fault_rate` > 0 to inject deterministic mechanical faults (DECISIONS
    D12) at that per-call probability, with seed=trial_index per trial, e.g.:
        uv run runner.py glm-faults z-ai/glm-4.6 20 0.5
    """
    from glm import MODEL  # the GLM default slug (z-ai/glm-4.6)

    label = argv[1] if len(argv) > 1 else "glm"
    model = argv[2] if len(argv) > 2 else MODEL
    n = int(argv[3]) if len(argv) > 3 else DEFAULT_N
    fault_rate = float(argv[4]) if len(argv) > 4 else 0.0

    make_scenario = None
    if fault_rate > 0:
        def make_scenario(i):
            return with_faults(ORDER_SCENARIO, rate=fault_rate, seed=i)

    arm = run_arm(label, model, n, make_scenario=make_scenario)
    print("\n" + "=" * 60)
    print(f"ARM {arm['label']}  ({arm['model']})   fault_rate={fault_rate}")
    print(f"completion rate : {arm['correct']}/{arm['n']} = {arm['rate']:.1%}")
    print(f"by_stop         : {arm['by_stop']}")
    print(f"trajectories    : runs/{arm['label']}/trial-NN.jsonl  (hand-read the misses)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
