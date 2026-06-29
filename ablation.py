"""ablation.py — the S4 ablation harness: baseline vs +error-recovery, with confidence intervals.

S3's `runner.run_arm` answers "how often does ONE arm complete?" — a raw k/N. S4 turns that into a
*measurement of a difference*: run two arms over the SAME injected faults, then report each arm's
Wilson interval and the Newcombe interval on the gap between them. That difference — with an honest
± and a straddles-zero / clears-zero verdict — is the gap-closure number this whole project exists
to produce.

*ablation* = turning one factor on or off (here, the error-recovery guardrail) while holding
everything else fixed, so the change in the outcome is attributable to that one factor.

The two arms (DECISIONS D8/D11 — the mechanism wraps the LOOP, never the task):
  - baseline        : the bare loop (recover=False)            — S1's control group
  - error_recovery  : harness-level retry of transient faults  — S4's first guardrail

Pairing: both arms run trial i against `with_faults(..., seed=i)`, so they face the *same* fault
pattern (DECISIONS D13: "N" = the number of distinct seeds; re-running a seed is reproducibility,
not more data). GLM's own stochasticity still varies which call lands on which fault draw — honest,
and part of where the spread comes from.

Run (needs OPENROUTER_API_KEY in .env — this makes real GLM calls):
    uv run ablation.py                       # GLM, n=40, fault_rate=0.6  (recommended operating point)
    uv run ablation.py z-ai/glm-4.6 40 0.6   # the same, explicit
    uv run ablation.py z-ai/glm-4.6 20 0.5   # cheaper S3-style sanity pass (likely overlaps -> null)
"""
from __future__ import annotations

import json
import os
import sys

from agent import TEMPERATURE
from agent import run as agent_run
from faults import with_faults
from runner import run_arm
from scenario import ORDER_SCENARIO, Scenario
from stats import excludes_zero, newcombe_diff, wilson

DEFAULT_N = 40        # distinct seeds; the recommended operating point for a legible result (D15)
DEFAULT_RATE = 0.6    # per-call fault probability; ~55-65% baseline leaves room above the CIs

# The arms, as config. Order matters: arm 0 is always the baseline reference; every later arm is
# measured against it. An arm is just a label + the run_kwargs that toggle one mechanism on — exactly
# the seam D11/D16 promised, now exercised by a THIRD arm-type (retry-nudge) at S6.
BASELINE_ARM = {"label": "baseline", "run_kwargs": {"recover": False}}
RECOVERY_ARM = {"label": "error_recovery", "run_kwargs": {"recover": True}}
NUDGE_ARM = {"label": "retry_nudge", "run_kwargs": {"nudge": True}}  # S6: the model-turn corrector


def run_arms(
    model: str,
    n: int,
    fault_rate: float,
    *,
    arms: list[dict],
    scenario: Scenario = ORDER_SCENARIO,
    make_scenario=None,
    fault_kind: str = "transient",
    run_fn=agent_run,
    runs_dir: str = "runs",
    out_name: str = "arms-summary.json",
    temperature: float = TEMPERATURE,
    verbose: bool = True,
    report: bool = True,
    write: bool = True,
) -> dict:
    """Run N arms over the SAME seeded faults; return each arm's rate + Wilson CI and every
    non-baseline arm's Newcombe gap vs `arms[0]` (the baseline reference).

    This is the general harness behind the project's ablations. `make_scenario(i)` builds the
    per-trial scenario (defaults to the transient-503 `with_faults`; S6 passes the malformed-call
    builder). `run_fn` is the per-trial driver (tests inject a fake for offline CI-wiring checks).
    Holds the fault fixed and varies only the mechanism per arm, so the gap is attributable to the
    mechanism (DECISIONS D16). Emits an `arms`-shaped summary; `run_ablation` repackages the 2-arm
    case into the legacy shape the S4/S5 figure reads.
    """
    if make_scenario is None:
        def make_scenario(i: int) -> Scenario:
            # Same fault pattern per trial index for EVERY arm -> a paired comparison.
            return with_faults(scenario, rate=fault_rate, seed=i)

    raw = [
        run_arm(arm["label"], model, n, make_scenario=make_scenario, run_kwargs=arm["run_kwargs"],
                run_fn=run_fn, runs_dir=runs_dir, temperature=temperature, verbose=verbose)
        for arm in arms
    ]

    base = raw[0]
    arm_summaries: list[dict] = []
    for i, r in enumerate(raw):
        lo, hi = wilson(r["correct"], r["n"])
        entry = {
            "label": r["label"], "correct": r["correct"], "n": r["n"], "rate": r["rate"],
            "wilson": [lo, hi], "by_stop": r["by_stop"],
            "recoveries": r.get("recoveries", 0), "nudges": r.get("nudges", 0),
        }
        if i > 0:  # every non-baseline arm gets a Newcombe interval vs the shared baseline
            d, d_lo, d_hi = newcombe_diff(base["correct"], base["n"], r["correct"], r["n"])
            entry["gap_vs_baseline"] = {"delta": d, "newcombe": [d_lo, d_hi],
                                        "excludes_zero": excludes_zero(d_lo, d_hi)}
        arm_summaries.append(entry)

    summary = {
        "model": model, "n": n, "fault_rate": fault_rate, "temperature": temperature,
        "fault_kind": fault_kind, "baseline_label": base["label"], "arms": arm_summaries,
    }
    if write:
        os.makedirs(runs_dir, exist_ok=True)
        summary["summary_path"] = os.path.join(runs_dir, out_name)
        with open(summary["summary_path"], "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
    if verbose and report:
        _report_arms(summary)
    return summary


def run_ablation(
    model: str,
    n: int,
    fault_rate: float,
    *,
    baseline: dict = BASELINE_ARM,
    mechanism: dict = RECOVERY_ARM,
    scenario: Scenario = ORDER_SCENARIO,
    run_fn=agent_run,
    runs_dir: str = "runs",
    temperature: float = TEMPERATURE,
    verbose: bool = True,
) -> dict:
    """The S4 two-arm convenience: baseline vs one mechanism over identical transient faults.

    A thin wrapper over `run_arms` that repackages the result into the original
    `{baseline, mechanism, gap_closure}` summary shape the S4/S5 figure (`chart.py` + the vendored
    `gap-closure-data.json`) reads — so generalizing to N arms didn't disturb the shipped deliverable.
    Writes `ablation-summary.json` under `runs_dir` and, if `verbose`, prints the gap-closure report.
    """
    s = run_arms(model, n, fault_rate, arms=[baseline, mechanism], scenario=scenario,
                 fault_kind="transient", run_fn=run_fn, runs_dir=runs_dir,
                 temperature=temperature, verbose=verbose, report=False, write=False)
    b, m = s["arms"][0], s["arms"][1]
    g = m["gap_vs_baseline"]
    summary = {
        "model": model, "n": n, "fault_rate": fault_rate, "temperature": temperature,
        "baseline": {"label": b["label"], "correct": b["correct"], "n": b["n"],
                     "rate": b["rate"], "wilson": b["wilson"], "by_stop": b["by_stop"],
                     "recoveries": b["recoveries"]},
        "mechanism": {"label": m["label"], "correct": m["correct"], "n": m["n"],
                      "rate": m["rate"], "wilson": m["wilson"], "by_stop": m["by_stop"],
                      "recoveries": m["recoveries"]},
        "gap_closure": {"delta": g["delta"], "newcombe": g["newcombe"],
                        "excludes_zero": g["excludes_zero"]},
    }
    os.makedirs(runs_dir, exist_ok=True)
    summary["summary_path"] = os.path.join(runs_dir, "ablation-summary.json")
    with open(summary["summary_path"], "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    if verbose:
        _report(summary)
    return summary


def _pct(x: float) -> str:
    return f"{x:.1%}"


def _report(s: dict) -> None:
    """Print the gap-closure result: each arm's rate + Wilson CI, then the Newcombe delta + verdict."""
    b, m, g = s["baseline"], s["mechanism"], s["gap_closure"]
    print("\n" + "=" * 66)
    print(f"S4 GAP-CLOSURE   model={s['model']}   n={s['n']}   fault_rate={s['fault_rate']}")
    print("-" * 66)
    print(f"  {b['label']:<15} {b['correct']:>3}/{b['n']:<3} = {_pct(b['rate']):>6}   "
          f"95% CI [{_pct(b['wilson'][0])}, {_pct(b['wilson'][1])}]")
    print(f"  {m['label']:<15} {m['correct']:>3}/{m['n']:<3} = {_pct(m['rate']):>6}   "
          f"95% CI [{_pct(m['wilson'][0])}, {_pct(m['wilson'][1])}]   "
          f"(harness recoveries: {m['recoveries']})")
    print("-" * 66)
    d, lo, hi = g["delta"], g["newcombe"][0], g["newcombe"][1]
    print(f"  gap closed: {d:+.1%}   Newcombe 95% CI [{lo:+.1%}, {hi:+.1%}]")
    if g["excludes_zero"]:
        print("  VERDICT: a real result — the interval clears 0; error-recovery lifts completion.")
    else:
        print("  VERDICT: NOT a result — the interval straddles 0 (the honesty rule). "
              "Raise fault_rate and/or add distinct seeds.")
    print("=" * 66)
    print(f"  summary -> {s['summary_path']}")


def _report_arms(s: dict) -> None:
    """Print the N-arm report: every arm's rate + Wilson CI, then each mechanism's Newcombe gap
    vs the shared baseline + a clears-zero / straddles-zero verdict (the honesty gate, D16)."""
    base = s["arms"][0]
    print("\n" + "=" * 72)
    print(f"GAP-CLOSURE  ({s['fault_kind']} fault)   model={s['model']}   "
          f"n={s['n']}   fault_rate={s['fault_rate']}")
    print("-" * 72)
    for a in s["arms"]:
        extra = ""
        if a["recoveries"]:
            extra += f"   (harness recoveries: {a['recoveries']})"
        if a["nudges"]:
            extra += f"   (corrective nudges: {a['nudges']})"
        print(f"  {a['label']:<16} {a['correct']:>3}/{a['n']:<3} = {_pct(a['rate']):>6}   "
              f"95% CI [{_pct(a['wilson'][0])}, {_pct(a['wilson'][1])}]{extra}")
    print("-" * 72)
    for a in s["arms"][1:]:
        g = a["gap_vs_baseline"]
        verdict = "a real result — clears 0" if g["excludes_zero"] else "NULL — straddles 0"
        print(f"  {a['label']:<16} vs {base['label']}: {g['delta']:+.1%}   "
              f"Newcombe 95% CI [{g['newcombe'][0]:+.1%}, {g['newcombe'][1]:+.1%}]   -> {verdict}")
    print("=" * 72)
    if "summary_path" in s:
        print(f"  summary -> {s['summary_path']}")


def main(argv: list[str]) -> int:
    """`uv run ablation.py [model] [n] [fault_rate]` — defaults to GLM, n=40, rate=0.6 (D15)."""
    from glm import MODEL

    model = argv[1] if len(argv) > 1 else MODEL
    n = int(argv[2]) if len(argv) > 2 else DEFAULT_N
    fault_rate = float(argv[3]) if len(argv) > 3 else DEFAULT_RATE
    run_ablation(model, n, fault_rate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
