# Methodology-Guardrails

## Purpose
A synthesis of the honesty machinery that governs every measurement in this project —
pre-registration, statistical method, oracle design, seed handling, and the rules for
reporting a null. For anyone asking "how do I know these results are trustworthy?" or
preparing to defend a methodology choice in an interview.

## Key understanding

### The fixed ruler: deterministic oracle, never an LLM judge

**Decision** — D2, [docs/DECISIONS.md](../docs/DECISIONS.md): task success is measured by
`oracle.py`, a plain-Python function that compares the model's submitted number to a
known-correct answer (158 for the standard scenario). The oracle reads from `ORDERS` and
`SHIP_RATES` directly — it is independent of the model's run. It cannot be fooled by a
wrong retrieval; it always reports the ground truth.

**Inference** — this is the structural separation the validation guardrail (S9) was designed
around: `oracle.py` reads from canonical data; `Scenario.validate` reads only from the
model's own run observations. The two compute the same arithmetic but from different inputs,
which is why `validate` can be fooled (wrong-record retrieval yields a self-consistent wrong
total that the oracle fails) and the oracle cannot.

### Statistical method: proportion CIs, not ±std

**Decision** — D7 + D16, [docs/DECISIONS.md](../docs/DECISIONS.md): completion rate is a
proportion, not a continuous measurement. The project uses:
- **Wilson interval** (`stats.py`, `wilson()`) — per-arm CI that stays sane at the edges
  (near 0% and 100%), unlike the Wald ±std which can run outside [0, 1].
- **Newcombe "square-and-add" interval** (`stats.py`, `newcombe_diff()`) — the CI on the
  *difference* between arms; carries Wilson's good edge behaviour into the gap estimate.
- **`excludes_zero` gate** (`stats.py`, `excludes_zero()`) — the mechanical honesty rule:
  if the Newcombe interval on the difference includes 0, the result is reported as a null,
  never a win. This gate was pre-committed (D7, written before any guardrail was built) and
  applied consistently in S4, S6, S8, S9, S10.

**Fact** — `stats.py` is pure Python with offline unit tests (`test_stats.py`); it is
exercised before any live run. The gate is not a judgement call applied after seeing results;
it is encoded in the harness (`ablation.py` checks `excludes_zero` per arm).

### N = distinct seeds, not trial count

**Decision** — D13 + D15, [docs/DECISIONS.md](../docs/DECISIONS.md): with deterministic
per-trial seeds (`seed=0..N-1`), completion under fault injection is dominated by the fault
*pattern*, not model stochasticity. Running two N=20 arms on seeds 0–19 is a paired comparison;
re-running seeds 0–19 again is reproducibility, not more data. This is why statistical power
comes from more *distinct* seeds, not more total trials on the same seeds.

**Inference** — this is a non-obvious property of the experiment design, and it has a
practical consequence: the recommended operating point (D15: rate 0.6, N=40) was chosen
because N=40 distinct seeds gives tighter Newcombe CIs than N=20, not because 40 trials
are intrinsically better than 20.

### Pre-registration and kill-triggers

**Decision** — D12, [docs/DECISIONS.md](../docs/DECISIONS.md): before the S3 diagnostic was
run, the team pre-committed to two routing rules:
- **Kill-trigger 1:** if GLM aces the clean task (≳85%), there is no natural gap; pivot to
  fault injection as the floor.
- **Kill-trigger 2 (bounded escalation):** if a hardened task still shows no gap after one
  escalation, declare no natural gap with evidence (D20).

Both triggers fired exactly as written. The S3 result (20/20 clean) triggered the injected-gap
path; S7's 8/8 hard-v1 and 8/8 hard-v2 triggered the no-natural-gap conclusion. **Inference**
— pre-committing routing rules is the structural mechanism that prevents the team from
rationalizing past inconvenient results: a null is a null if it's pre-agreed, not re-framed
as "we need one more run."

### What counted as a null — and why S6 is a real finding

**Fact** — S6 measured +0.0 pp [−16.1, +16.1] for both retry-nudge and error-recovery vs
baseline on the malformed-call testbed (D19, [docs/DECISIONS.md](../docs/DECISIONS.md)).
Both intervals straddle zero → both are nulls by the pre-committed gate. The null was
published as the result, not suppressed.

**Inference** — this null is a stronger finding than it might appear: the retry-nudge arm
*did* issue 26 corrective re-prompts (the mechanism worked), but GLM self-corrected from the
400-error hint in the tool result *before* the nudge was needed, so the mechanism had no
work to do. This establishes a *boundary* on where guardrails help: only where the model
cannot self-correct.

### What would have falsified the project's claim

**Inference** — the thesis (each failure class has a matched guardrail that provably lifts
completion) would have been falsified by any of:
- A Newcombe interval straddling zero on a "real lift" arm after an honest N (none occurred
  for the four designed-to-lift arms: S4, S8, S9, S10).
- Evidence that the validator read `scenario.ground_truth` (the bright line; verified in code
  review of S9 and D23's re-verification).
- A guardrail arm that raised completion via a route other than the one it targets (e.g.,
  error-recovery suppressing a malformed fault by chance) — structural separation of fault
  types prevents this (D19: the `is_retryable` check classifies 503 vs 400 at the harness
  level).

**Unresolved** — no independent replication has been run; all measurements are single-team,
single-codebase, and the fault injectors are deterministic (seeded), so the same seeds would
reproduce but a different seed set is untested at scale.

### The honesty caption rule

**Fact** — every figure in `docs/figures/` carries a caption that explicitly states whether
the gap is injected or natural. The rule is encoded in `chart.py`'s `caption_fn` parameter:
the S4/S5 figure says "gap is INJECTED · 104 transient 503s absorbed"; S8/S9/S10 figures
label the gap as natural (no injection). The injected vs. natural distinction was never
dropped or softened in any figure. **Decision** — D1, [docs/DECISIONS.md](../docs/DECISIONS.md):
the framing is always "reproduced and measured a known primitive," never "invented."

## Sources
- [docs/DECISIONS.md](../docs/DECISIONS.md) — D1, D2, D3, D5, D7, D12, D13, D15, D16, D19, D22, D23 (the methodology decisions, each with options weighed)
- [docs/LEARNING.md](../docs/LEARNING.md) — plain-English teaching notes on CIs, proportion statistics, and the oracle design
- [CLAUDE.md](../CLAUDE.md) — "Methodology guardrails (load-bearing — do not drift)" section
- [PROJECT.md](../PROJECT.md) — "Boundaries" section restates the load-bearing methodology rules

## Uncertainties & contradictions
- **Unresolved** — temperature 0.7 was fixed (D5) because GLM is stochastic regardless; the precise effect of temperature on the measured gaps is not characterized. A temperature-sweep sensitivity analysis was not conducted.
- **Unresolved** — S10's "first-evidence anchoring" in `Scenario.validate` (recomputes from the first retrieved value of each field, not the most recent) was a design property disclosed but not altered mid-experiment; its effect on the 10% wrong-record slice is an acknowledged limitation.

## Related pages
- [Results-Synthesis](Results-Synthesis.md)
- [Experiment-Harness](Experiment-Harness.md)
- [History](History.md)

## Relevance to current work
The project is closed; these guardrails are the durable rules for any follow-on project. Any
reuse of this harness (live capability ladder, self-hosted endpoint — D24 roads not taken)
should inherit these rules wholesale, particularly the `excludes_zero` gate and the
injected-vs-natural disclosure requirement.

_Last reviewed: 2026-07-26_
