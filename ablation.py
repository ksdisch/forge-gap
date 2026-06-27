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

# The arms compared. Order matters: arm 0 is the baseline reference, arm 1 the mechanism.
# Adding retry-nudge later is one more entry here + one more toggle in agent.run — no rewrite.
BASELINE_ARM = {"label": "baseline", "run_kwargs": {"recover": False}}
RECOVERY_ARM = {"label": "error_recovery", "run_kwargs": {"recover": True}}


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
    """Run the baseline + mechanism arms over identical seeded faults; return rates + CIs.

    `run_fn` is the per-trial driver (defaults to the real `agent.run`; tests inject a fake so the
    aggregation + CI wiring can be verified offline, with no API calls). Writes an
    `ablation-summary.json` under `runs_dir` and, if `verbose`, prints the gap-closure report.
    """
    def make_scenario(i: int) -> Scenario:
        # Same fault pattern per trial index for BOTH arms -> a paired comparison.
        return with_faults(scenario, rate=fault_rate, seed=i)

    arms: dict[str, dict] = {}
    for arm in (baseline, mechanism):
        arms[arm["label"]] = run_arm(
            arm["label"], model, n,
            make_scenario=make_scenario, run_kwargs=arm["run_kwargs"],
            run_fn=run_fn, runs_dir=runs_dir, temperature=temperature, verbose=verbose)

    b, m = arms[baseline["label"]], arms[mechanism["label"]]
    b_lo, b_hi = wilson(b["correct"], b["n"])
    m_lo, m_hi = wilson(m["correct"], m["n"])
    d, d_lo, d_hi = newcombe_diff(b["correct"], b["n"], m["correct"], m["n"])

    summary = {
        "model": model, "n": n, "fault_rate": fault_rate, "temperature": temperature,
        "baseline": {"label": baseline["label"], "correct": b["correct"], "n": b["n"],
                     "rate": b["rate"], "wilson": [b_lo, b_hi], "by_stop": b["by_stop"],
                     "recoveries": b.get("recoveries", 0)},
        "mechanism": {"label": mechanism["label"], "correct": m["correct"], "n": m["n"],
                      "rate": m["rate"], "wilson": [m_lo, m_hi], "by_stop": m["by_stop"],
                      "recoveries": m.get("recoveries", 0)},
        "gap_closure": {"delta": d, "newcombe": [d_lo, d_hi],
                        "excludes_zero": excludes_zero(d_lo, d_hi)},
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
