"""pilot.py — the S7 natural-gap PILOT (DECISIONS D20).

The cheap de-risk before any full experiment: run the **bare baseline** (no guardrails) on a
**hardened** task, **clean** — no injected faults — and ask one gating question:

    Does the hardened task break GLM-4.6 on its own merits, and if so, of what TYPE?

It does NOT run the guardrail arms — those are premature until we know the failure type (see the
failure-type -> guardrail table in DECISIONS D20). It just reports the completion rate and surfaces
every miss with its trajectory path, so we can hand-read and classify each one:

    transient-error / malformed-call / wrong-answer-no-error / no_submit / max_steps

Two difficulty levels (DECISIONS D20):
    v1  — a 4-lookup chain through 15 look-alike records (find the order by description).
    v2  — the escalation: a 5-lookup chain (adds per-zone tax) through ~25 records with a
          near-duplicate-customer distractor.

`max_steps` is raised per version so a longer chain has room to finish — a "miss" should mean GLM got
it wrong, never that it ran out of steps (a budget artifact is not a natural failure).

Run (needs OPENROUTER_API_KEY in .env — this makes real GLM calls):
    uv run pilot.py            # v1, N=8
    uv run pilot.py v2         # v2, N=8
    uv run pilot.py v2 8 14    # v2, explicit N and max_steps
"""
from __future__ import annotations

import sys

from glm import MODEL
from runner import run_arm
from scenario_hard import (
    GROUND_TRUTH,
    GROUND_TRUTH_V2,
    HARD_SCENARIO,
    HARD_SCENARIO_V2,
    TARGET_CUSTOMER,
    TARGET_CUSTOMER_V2,
    TARGET_ZONE,
    TARGET_ZONE_V2,
)

PILOT_N = 8  # signal detection, not a CI-grade measurement (that's the full run, if we proceed)

VERSIONS = {
    "v1": {"scenario": HARD_SCENARIO, "label": "baseline-hard", "max_steps": 12,
           "ground_truth": GROUND_TRUTH, "customer": TARGET_CUSTOMER, "zone": TARGET_ZONE},
    "v2": {"scenario": HARD_SCENARIO_V2, "label": "baseline-hard-v2", "max_steps": 14,
           "ground_truth": GROUND_TRUTH_V2, "customer": TARGET_CUSTOMER_V2, "zone": TARGET_ZONE_V2},
}


def main(argv: list[str]) -> int:
    args = argv[1:]
    version = "v1"
    if args and args[0] in VERSIONS:   # optional leading version token; otherwise default v1
        version, args = args[0], args[1:]
    cfg = VERSIONS[version]
    n = int(args[0]) if len(args) > 0 else PILOT_N
    max_steps = int(args[1]) if len(args) > 1 else cfg["max_steps"]

    print(f"S7 PILOT [{version}] — clean (no faults), bare baseline, HARDENED task")
    print(f"  task       : grand total for the {cfg['customer']} order shipping to {cfg['zone']}")
    print(f"  model={MODEL}  N={n}  max_steps={max_steps}  ground_truth={cfg['ground_truth']}\n")

    arm = run_arm(cfg["label"], MODEL, n, scenario=cfg["scenario"],
                  run_kwargs={"max_steps": max_steps})

    misses = [t for t in arm["trials"] if not t["correct"]]
    print("\n" + "=" * 74)
    print(f"PILOT RESULT [{version}]   {arm['correct']}/{arm['n']} = {arm['rate']:.1%}   "
          f"by_stop={arm['by_stop']}")
    print("-" * 74)
    if not misses:
        print("  No misses — GLM aced the hardened task. No natural gap at this difficulty.")
        print("  -> route A (declare done) or escalate the lever once more (DECISIONS D20).")
    else:
        print(f"  {len(misses)} miss(es) to hand-read & classify (open each trajectory):")
        for t in misses:
            print(f"    stop={t['stop']:<10} submitted={t.get('submitted')!r:>8} "
                  f"expected={t['expected']!r}   ->  {t['trajectory']}")
        print("\n  Classify each by the DECISIONS-D20 table, then route A / full-B / escalate-to-C.")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
