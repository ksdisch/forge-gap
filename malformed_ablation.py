"""malformed_ablation.py — the S6 three-arm ablation on the MALFORMED-call testbed.

S4 measured one guardrail (error-recovery) against one fault (transient 503s). S6 measures the
SECOND guardrail — retry-nudge — against the fault it is built for: a malformed call (the model's own
call is wrong). The deliverable is a single, legible 3-bar ablation that holds the fault fixed and
varies only the mechanism (DECISIONS D19):

    baseline         no mechanism                                  — the control
    +error-recovery  harness retries transient faults (no turn)    — expected ≈ baseline here, because
                                                                      a malformed call is PERMANENT,
                                                                      not transient, so it is never
                                                                      retried — the in-experiment
                                                                      control that *shows* the wrong
                                                                      guardrail does nothing
    +retry-nudge     re-prompts the MODEL to fix its call (a turn) — the matched guardrail; expected
                                                                      to lift completion

All three arms run trial i against `with_malformed_faults(..., seed=i)`, so they face the same armed
tools per trial — a paired comparison. Each non-baseline arm reports its Newcombe gap vs the shared
baseline with the same straddles-zero honesty gate (D16); a null is reported as a null.

Run (needs OPENROUTER_API_KEY in .env — real GLM calls):
    uv run malformed_ablation.py                       # GLM, n=40, rate=0.6 (the operating point)
    uv run malformed_ablation.py z-ai/glm-4.6 6 0.6    # a cheap pilot (verify wiring + that a gap exists)
    uv run malformed_ablation.py z-ai/glm-4.6 40 0.8   # tune the rate if the baseline self-corrects
"""
from __future__ import annotations

import sys

from ablation import BASELINE_ARM, NUDGE_ARM, RECOVERY_ARM, run_arms
from agent import TEMPERATURE
from faults import with_malformed_faults
from scenario import ORDER_SCENARIO, Scenario

DEFAULT_N = 40        # distinct seeds (D15: "N" = number of distinct seeds, not re-runs)
DEFAULT_RATE = 0.6    # per-seed probability EACH lookup tool is armed with a malformed rejection

# Arm 0 is always the baseline reference. The wrong-guardrail control (error-recovery) sits between
# baseline and the matched guardrail (retry-nudge) so the report reads baseline -> null -> lift.
S6_ARMS = [BASELINE_ARM, RECOVERY_ARM, NUDGE_ARM]


def run_malformed_ablation(
    model: str,
    n: int,
    fault_rate: float,
    *,
    scenario: Scenario = ORDER_SCENARIO,
    runs_dir: str = "runs",
    temperature: float = TEMPERATURE,
    verbose: bool = True,
) -> dict:
    """Run the S6 baseline / +error-recovery / +retry-nudge arms over identical malformed faults."""
    def make_scenario(i: int) -> Scenario:
        return with_malformed_faults(scenario, rate=fault_rate, seed=i)

    return run_arms(
        model, n, fault_rate, arms=S6_ARMS, make_scenario=make_scenario, fault_kind="malformed",
        runs_dir=runs_dir, out_name="malformed-ablation-summary.json",
        temperature=temperature, verbose=verbose,
    )


def main(argv: list[str]) -> int:
    """`uv run malformed_ablation.py [model] [n] [fault_rate]` — defaults to GLM, n=40, rate=0.6."""
    from glm import MODEL

    model = argv[1] if len(argv) > 1 else MODEL
    n = int(argv[2]) if len(argv) > 2 else DEFAULT_N
    fault_rate = float(argv[3]) if len(argv) > 3 else DEFAULT_RATE
    run_malformed_ablation(model, n, fault_rate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
