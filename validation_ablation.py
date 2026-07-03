"""validation_ablation.py — the S9 STACKED 2-arm ablation on a weak model (the validation guardrail).

S8 showed a weak model (mistral-nemo) has a natural gap: on the clean task it computes the answer but
never calls the terminal tool (submit-nudge closes that no-submit gap, +75 pp). Behind submit-nudge a
RESIDUAL remained — the model submits `140` (the item total, shipping forgotten): a wrong-answer-no-error
/ VALIDATION gap submit-nudge structurally can't touch. S9 closes that residual with a NEW validation
guardrail: recompute the total from the model's OWN retrieved evidence and re-prompt on a mismatch (never
the oracle's ground truth — a self-consistency check, not an answer key; DECISIONS D22).

Because the model's bare baseline is ~0% (it never submits), the validation gap is MASKED until
submit-nudge lifts it into view. So this is a STACKED ablation — hold submit-nudge fixed, toggle validation:

    submit_nudge   re-prompt a stalled run to submit           — the REFERENCE (the layer below)
    validation     submit_nudge + validate                     — the matched guardrail; expected to lift

Both arms run the identical CLEAN `ORDER_SCENARIO` (no fault injection). The mechanism arm's Newcombe gap
is measured vs the submit_nudge reference (arm 0), with the straddles-zero honesty gate (D16); a null is
reported as a null. The bare 0% baseline (from S8) is shown only as figure context — it isn't re-run here,
because with nothing submitted there is nothing for validation to check.

Run (needs OPENROUTER_API_KEY in .env — real model calls):
    uv run validation_ablation.py                              # mistral-nemo, n=40, clean
    uv run validation_ablation.py mistralai/mistral-nemo 8     # a cheap pilot (verify the lift exists)
"""
from __future__ import annotations

import sys

from ablation import SUBMIT_NUDGE_ARM, VALIDATION_ARM, run_arms
from agent import TEMPERATURE
from scenario import ORDER_SCENARIO, Scenario

DEFAULT_MODEL = "mistralai/mistral-nemo"  # the S8 weak model (its residual is the pure arithmetic slip)
DEFAULT_N = 40                            # D22: N=40 is robust; N=20 is knife-edge for this ~25pp residual

# Arm 0 is the reference (submit_nudge — the layer that makes the validation gap visible); arm 1 stacks
# validation on top. run_arms computes arm 1's Newcombe gap vs arm 0 = validation's INCREMENTAL lift.
S9_ARMS = [SUBMIT_NUDGE_ARM, VALIDATION_ARM]


def run_validation_ablation(
    model: str,
    n: int,
    *,
    scenario: Scenario = ORDER_SCENARIO,
    runs_dir: str = "runs",
    temperature: float = TEMPERATURE,
    verbose: bool = True,
) -> dict:
    """Run the S9 submit_nudge (reference) vs submit_nudge+validation arms over the identical CLEAN task."""
    def make_scenario(i: int) -> Scenario:
        return scenario  # no fault injection — the clean task, every trial (S9 / DECISIONS D22)

    return run_arms(
        model, n, 0.0, arms=S9_ARMS, make_scenario=make_scenario, fault_kind="none",
        runs_dir=runs_dir, out_name="validation-ablation-summary.json",
        temperature=temperature, verbose=verbose,
    )


def main(argv: list[str]) -> int:
    """`uv run validation_ablation.py [model] [n]` — defaults to mistral-nemo, n=40, clean (no injection)."""
    model = argv[1] if len(argv) > 1 else DEFAULT_MODEL
    n = int(argv[2]) if len(argv) > 2 else DEFAULT_N
    run_validation_ablation(model, n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
