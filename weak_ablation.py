"""weak_ablation.py — the S8 clean 3-arm ablation on a WEAK model (the natural-gap experiment).

S3–S7 studied GLM-4.6, which has no natural gap, so guardrails had to be measured against *injected*
faults. S8 flips the variable instead: hold the task fixed and CLEAN (no injection), and swap in a
weaker model whose own failures are natural. The fit pilots found mistral-nemo computes the right
answer but never calls the terminal tool — a `no_submit` / "protocol" gap. This ablation measures the
NEW submit-nudge guardrail against that natural failure, with retry-nudge as the in-experiment control
that should do nothing — the guardrail-specificity story (DECISIONS D21):

    baseline       no mechanism                                  — the control
    +retry-nudge   re-prompts the model after a FAILED call      — expected ≈ baseline here, because a
                                                                    no-submit is NOT a failed call, so the
                                                                    nudge never fires (the wrong guardrail,
                                                                    shown to do nothing)
    +submit-nudge  re-prompts the model when it never SUBMITTED  — the matched guardrail; expected to lift

The task is the frozen, CLEAN `ORDER_SCENARIO` — no fault injection at all (`fault_kind="none"`). Every
arm runs the identical task; the only variation is the model's own stochasticity (as in S3). Each
non-baseline arm reports its Newcombe gap vs the shared baseline with the straddles-zero honesty gate
(D16); a null is reported as a null.

Run (needs OPENROUTER_API_KEY in .env — real model calls):
    uv run weak_ablation.py                                      # mistral-nemo, n=30, clean
    uv run weak_ablation.py mistralai/mistral-nemo 8             # a cheap pilot (verify the lift exists)
    uv run weak_ablation.py meta-llama/llama-3.1-8b-instruct 30  # a different weak model
"""
from __future__ import annotations

import sys

from ablation import BASELINE_ARM, NUDGE_ARM, SUBMIT_NUDGE_ARM, run_arms
from agent import TEMPERATURE
from scenario import ORDER_SCENARIO, Scenario

DEFAULT_MODEL = "mistralai/mistral-nemo"  # the S8 weak model (the fit pilot's protocol-gap case)
DEFAULT_N = 30                            # distinct trials; the only variation is model stochasticity

# Arm 0 is always the baseline reference. retry-nudge (the wrong guardrail here) sits between baseline
# and submit-nudge (the matched guardrail) so the report reads baseline -> null -> lift.
S8_ARMS = [BASELINE_ARM, NUDGE_ARM, SUBMIT_NUDGE_ARM]


def run_weak_ablation(
    model: str,
    n: int,
    *,
    scenario: Scenario = ORDER_SCENARIO,
    runs_dir: str = "runs",
    temperature: float = TEMPERATURE,
    verbose: bool = True,
) -> dict:
    """Run the S8 baseline / +retry-nudge / +submit-nudge arms over the identical CLEAN task."""
    def make_scenario(i: int) -> Scenario:
        return scenario  # no fault injection — the clean task, every trial (S8 / DECISIONS D21)

    return run_arms(
        model, n, 0.0, arms=S8_ARMS, make_scenario=make_scenario, fault_kind="none",
        runs_dir=runs_dir, out_name="weak-ablation-summary.json",
        temperature=temperature, verbose=verbose,
    )


def main(argv: list[str]) -> int:
    """`uv run weak_ablation.py [model] [n]` — defaults to mistral-nemo, n=30, clean (no injection)."""
    model = argv[1] if len(argv) > 1 else DEFAULT_MODEL
    n = int(argv[2]) if len(argv) > 2 else DEFAULT_N
    run_weak_ablation(model, n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
