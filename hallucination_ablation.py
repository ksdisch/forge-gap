"""hallucination_ablation.py — the S10 UN-stacked 2-arm ablation: validation on a MESSY wrong-answer gap.

S9 measured the validation guardrail on its best-case testbed: mistral-nemo's residual was 100% pure
arithmetic slip (retrieved both inputs, forgot to add), so the self-consistency check caught 6/6 (+25 pp).
S10 is the stress test parked at S9 (DECISIONS D23): the SAME guardrail, byte-for-byte, on
llama-3.1-8b — whose natural failure on the clean task is HALLUCINATION (the S8 fit-pilot scored 0/8,
submitting garbage like `1234.56` and twice the literal formula string "item_total_usd + ship_rate").

Two design deltas vs S9 (D23):
  1. UN-stacked. llama submits on its own (garbage, but it calls the terminal tool), so the no-submit
     gap doesn't mask the validation gap — the reference arm is the BARE baseline and validation
     toggles directly (VALIDATION_ONLY_ARM: validate=True, no submit_nudge).
  2. The decomposition metric. Hand-read every miss and split the gap into (i) validation-catchable —
     retrieved the evidence, submitted an inconsistent number — vs (ii) un-validatable — never
     retrieved it (the validator accepts by design rather than guess) or non-numeric (passed through;
     the oracle fails it). Slice (ii) is D22's disclosed blind spot, now MEASURED.

Both arms run the identical CLEAN `ORDER_SCENARIO` (no fault injection). Wilson per arm, Newcombe gap
vs baseline, straddles-zero honesty gate (D16); a null is reported as a null — "even a small X pp
recovered, Y pp structurally un-validatable" is the measurement either way.

Run (needs OPENROUTER_API_KEY in .env — real model calls):
    uv run hallucination_ablation.py                                    # llama-3.1-8b, n=40, clean
    uv run hallucination_ablation.py meta-llama/llama-3.1-8b-instruct 8 # the D23 fit-pilot (~pennies)
"""
from __future__ import annotations

import sys

from ablation import BASELINE_ARM, VALIDATION_ONLY_ARM, run_arms
from agent import TEMPERATURE
from scenario import ORDER_SCENARIO, Scenario

DEFAULT_MODEL = "meta-llama/llama-3.1-8b-instruct"  # the S8 capability-cliff model (hallucinates; D21)
DEFAULT_N = 40                                      # provisional — D23 sizes the full N from the pilot

# Arm 0 is the bare baseline (llama submits unaided, so nothing is masked); arm 1 toggles validation
# alone. run_arms computes arm 1's Newcombe gap vs arm 0 = validation's lift on the messy gap.
S10_ARMS = [BASELINE_ARM, VALIDATION_ONLY_ARM]


def run_hallucination_ablation(
    model: str,
    n: int,
    *,
    scenario: Scenario = ORDER_SCENARIO,
    runs_dir: str = "runs",
    temperature: float = TEMPERATURE,
    verbose: bool = True,
) -> dict:
    """Run the S10 baseline vs +validation arms over the identical CLEAN task."""
    def make_scenario(i: int) -> Scenario:
        return scenario  # no fault injection — the clean task, every trial (S10 / DECISIONS D23)

    return run_arms(
        model, n, 0.0, arms=S10_ARMS, make_scenario=make_scenario, fault_kind="none",
        runs_dir=runs_dir, out_name="hallucination-ablation-summary.json",
        temperature=temperature, verbose=verbose,
    )


def main(argv: list[str]) -> int:
    """`uv run hallucination_ablation.py [model] [n]` — defaults to llama-3.1-8b, n=40, clean."""
    model = argv[1] if len(argv) > 1 else DEFAULT_MODEL
    n = int(argv[2]) if len(argv) > 2 else DEFAULT_N
    run_hallucination_ablation(model, n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
