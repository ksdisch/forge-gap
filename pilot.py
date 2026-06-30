"""pilot.py — the S7 natural-gap PILOT (DECISIONS D20).

The cheap de-risk before any full experiment: run the **bare baseline** (no guardrails) on the
**hardened** task (`scenario_hard.HARD_SCENARIO`), **clean** — no injected faults — and ask one
gating question:

    Does the hardened task break GLM-4.6 on its own merits, and if so, of what TYPE?

It does NOT run the guardrail arms — those are premature until we know the failure type (see the
failure-type -> guardrail table in DECISIONS D20). It just reports the completion rate and surfaces
every miss with its trajectory path, so we can hand-read and classify each one:

    transient-error / malformed-call / wrong-answer-no-error / no_submit / max_steps

`MAX_STEPS` is raised to PILOT_MAX_STEPS so a longer chain has room to finish — a "miss" should mean
GLM got it wrong, never that it ran out of steps (a budget artifact is not a natural failure).

Run (needs OPENROUTER_API_KEY in .env — this makes real GLM calls):
    uv run pilot.py
    uv run pilot.py 8 12      # explicit N, max_steps
"""
from __future__ import annotations

import sys

from glm import MODEL
from runner import run_arm
from scenario_hard import GROUND_TRUTH, HARD_SCENARIO, TARGET_CUSTOMER, TARGET_ZONE

PILOT_N = 8           # signal detection, not a CI-grade measurement (that's the full run, if we proceed)
PILOT_MAX_STEPS = 12  # generous headroom for the ~5-call happy path, so misses aren't budget artifacts


def main(argv: list[str]) -> int:
    n = int(argv[1]) if len(argv) > 1 else PILOT_N
    max_steps = int(argv[2]) if len(argv) > 2 else PILOT_MAX_STEPS

    print("S7 PILOT — clean (no faults), bare baseline, HARDENED task")
    print(f"  task       : grand total for the {TARGET_CUSTOMER} order shipping to {TARGET_ZONE}")
    print(f"  model={MODEL}  N={n}  max_steps={max_steps}  ground_truth={GROUND_TRUTH}\n")

    arm = run_arm("baseline-hard", MODEL, n, scenario=HARD_SCENARIO,
                  run_kwargs={"max_steps": max_steps})

    misses = [t for t in arm["trials"] if not t["correct"]]
    print("\n" + "=" * 74)
    print(f"PILOT RESULT   {arm['correct']}/{arm['n']} = {arm['rate']:.1%}   by_stop={arm['by_stop']}")
    print("-" * 74)
    if not misses:
        print("  No misses — GLM aced the hardened task. No natural gap at this difficulty.")
        print("  -> route A (declare done) or escalate the lever once (DECISIONS D20).")
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
