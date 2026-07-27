# Results-Synthesis

## Purpose
One place to read what forge-gap actually measured end to end: every headline number,
its pre-registered prediction, the observed outcome, and what each result means for the
project's thesis. For anyone trying to defend or critique the measurements without reading
all five per-stage figures plus the decision ledger.

## Key understanding

### The four measured gaps — pre-registration vs. observed

| Failure class | Matched guardrail | Stage | Pre-registered expectation | Observed result | Verdict |
|---|---|---|---|---|---|
| Transient 503 (injected, rate 0.6) | error-recovery | S4 | gap should clear zero; Newcombe CI excludes 0 | **+32.5 pp** [+17.3, +48.0] — GLM-4.6, N=40 | **REAL** |
| Malformed call (injected, rate 0.6) | retry-nudge | S6 | pilot warned of a null; GLM may self-heal | **null** (+0.0 pp, [−16.1, +16.1]) — GLM self-corrects in one turn | **NULL** (pre-registered risk) |
| No-submit (natural, clean task) | submit-nudge | S8 | lift expected; retry-nudge null in same run (specificity control) | **+75.0 pp** [+47.8, +88.8] — mistral-nemo, N=20 | **REAL** |
| Wrong-answer / arithmetic slip (natural) | validation | S9 | lift on nemo's clean 140→158 slip; possibly catches all 5 misses | **+25.0 pp** [+11.1, +40.2] — mistral-nemo, N=40 | **REAL** |
| Wrong-answer / hallucination (natural) | validation (un-stacked) | S10 | recovers checkable slice; residual expected due to blind spot | **+45.0 pp** [+28.2, +60.2] — llama-3.1-8b, N=40 | **REAL (partial)** |

**Fact** — all point estimates and Newcombe CIs traced directly to vendored data files:
`docs/figures/gap-closure-data.json` (S4), `docs/figures/malformed-gap-data.json` (S6),
`docs/figures/weak-gap-data.json` (S8), `docs/figures/validation-data.json` (S9),
`docs/figures/hallucination-gap-data.json` (S10).

### What the injected-gap chart shows — and does not

The project's first headline figure (`docs/figures/gap-closure.png`) shows two bars:
baseline 67.5% vs +error-recovery 100% on GLM-4.6, N=40, fault-rate 0.6.

**Fact** — the gap is **injected**: a deterministic 503-style fault at a published rate; it
is not GLM's natural failure. The figure carries this disclosure in its caption: "gap is
INJECTED (controlled fault-recovery testbed) · 104 transient 503s absorbed." **Decision** —
D12, [docs/DECISIONS.md](../docs/DECISIONS.md): the injected testbed was the pre-agreed
floor when kill-trigger 1 fired (GLM scored 20/20 clean at S3 — no natural gap to close).

What the figure does **not** show: it does not claim GLM fails naturally, and it does not
show a guardrail bar for GLM's clean task (there was none to measure — S7 proved GLM aces
hardened tasks too; **Decision** D24, [docs/DECISIONS.md](../docs/DECISIONS.md)).

### Capability × guardrail: the capstone ladder

The S11 capstone figure (`docs/figures/capstone-ladder.png`) synthesizes three models on
the clean task:

| Model | Baseline (clean task) | + matched guardrails | Gap |
|---|---|---|---|
| GLM-4.6 (strong) | 100% [83.9%, 100%] | no bar — nothing to close | — |
| mistral-nemo (mid) | 0% [0.0%, 16.1%] | +submit-nudge+validation: 100% [91.2%, 100%] | +100.0 pp [+81.7, +100.0] (cross-run) |
| llama-3.1-8b (weak) | 0% [0.0%, 8.8%] | +validation: 45% [30.7%, 60.2%] | +45.0 pp [+28.2, +60.2] (same run) |

**Fact** — numbers traced to `docs/figures/capstone-data.json`. **Decision** — D24,
[docs/DECISIONS.md](../docs/DECISIONS.md): the ladder is derived from already-measured
data, not a new experiment; GLM draws one bar because no guardrail arm was ever run on its
clean task.

**Inference** — the ladder supports the thesis that the weaker the model, the more a matched
guardrail buys — but only up to the limit of what the guardrail can structurally see (llama's
45% ceiling is not a failure of the design; it is the blind spot, measured and decomposed).

### The S10 residual decomposition — the blind spot, quantified

S10's stage-specific contribution is decomposing the 55% llama-8b residual that validation
cannot recover:

| Residual slice | Share | Why structurally un-recoverable |
|---|---|---|
| Never retrieved the rate | 35% (14/40) | validator accepts-by-design (no evidence to recompute from) |
| Wrong-record retrieval | 10% (4/40) | validator fooled — self-consistent but wrong total (152 vs 158) |
| Non-numeric submission | 7.5% (3/40) | validator passes through; oracle fails |
| Never submitted | 2.5% (1/40) | nothing to validate |

**Fact** — decomposition traced to [docs/DECISIONS.md](../docs/DECISIONS.md) D23 (hand-read
of every validation-arm miss). **Inference** — this decomposition turns D22's disclosed blind
spot from a caveat into a number: the validator closes consistency failures but not evidence
failures.

### Guardrail specificity — the in-experiment controls

Three experiments included a deliberately wrong guardrail as an in-experiment control:

- S6: error-recovery ≈ baseline on malformed faults (structural — a permanent fault is never
  retried by the recovery guardrail). **Fact** — D19, [docs/DECISIONS.md](../docs/DECISIONS.md).
- S8: retry-nudge = 0 nudges fired on mistral-nemo's no-submit gap (a missing call is not a
  failed call). **Fact** — `docs/figures/weak-gap-data.json`, `retry_nudge` arm, `nudges: 0`.
- S9: validation's own mechanism was verified honest — it fired on 5 of 5 `140` submissions and
  never read `scenario.ground_truth`. **Fact** — D22 measured result, [docs/DECISIONS.md](../docs/DECISIONS.md).

**Inference** — specificity held in every experiment: the guardrail matched to a failure class
moves the number; unmatched guardrails null.

## Sources
- [docs/DECISIONS.md](../docs/DECISIONS.md) — D12, D13, D17, D19, D21, D22, D23, D24 (all measured results + pre-registration)
- [docs/figures/gap-closure-data.json](../docs/figures/gap-closure-data.json)
- [docs/figures/weak-gap-data.json](../docs/figures/weak-gap-data.json)
- [docs/figures/validation-data.json](../docs/figures/validation-data.json)
- [docs/figures/hallucination-gap-data.json](../docs/figures/hallucination-gap-data.json)
- [docs/figures/capstone-data.json](../docs/figures/capstone-data.json)
- [docs/ROADMAP.md](../docs/ROADMAP.md) — stage table with per-stage outcome summaries
- [PROJECT.md](../PROJECT.md) — headline results table

## Uncertainties & contradictions
- **Unresolved** — the malformed-gap figure data file (`docs/figures/malformed-gap-data.json`) was not read directly for this page; the null result (+0.0 pp, [−16.1, +16.1]) is sourced from D19's measured-result section rather than the vendored JSON.
- **Inference** — the nemo cross-run Newcombe (+100 pp [+81.7, +100.0]) combines the S8 baseline (N=20) and S9 guardrail arm (N=40) from two separate experiments; D24 explicitly discloses this as cross-run and explains why it is statistically sound.

## Related pages
- [Methodology-Guardrails](Methodology-Guardrails.md)
- [Experiment-Harness](Experiment-Harness.md)
- [History](History.md)

## Relevance to current work
The project is closed (S11, D24). This page is the durable one-stop record of what was
measured — useful for portfolio defense, future project seeding (what the remaining 55% of
llama's gap would require), and as the entry point for any revisit under the D24 roads not
taken.

_Last reviewed: 2026-07-26_
