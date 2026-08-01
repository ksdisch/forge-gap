# Matched Guardrails: Reproducing and Measuring Four Reliability Primitives for LLM Tool-Use Agents

**The forge-gap experiments** · Kyle Disch · 2026-07-08

---

## Abstract

LLM agents fail multi-step tool tasks for mechanical reasons — a flaky tool, a malformed call, an answer computed but never submitted, a wrong number submitted with no error at all. Practitioners bolt on reliability guardrails (retries, corrective re-prompts, output validators) without measuring what each one buys. We reproduce four such guardrails — error-recovery, retry-nudge, submit-nudge, and evidence-validation, all established practice rather than inventions of ours — and measure each against the one failure class it targets, on a fixed lookup-then-compute tool task, graded by a deterministic oracle (never an LLM judge), with a Wilson 95% interval per arm, a Newcombe 95% interval on every between-arm difference, and a pre-registered rule that an interval straddling zero is reported as a null. On GLM-4.6, which shows no natural gap, failures had to be injected (disclosed as manufactured): harness-level error-recovery closed an injected transient-fault gap by **+32.5 percentage points** (95% CI [+17.3, +48.0]), while retry-nudge measured a **null** on injected malformed calls (+0.0 pp [−16.1, +16.1]) — the model self-corrects. On weaker models the gaps are natural: submit-nudge lifted mistral-nemo from 0% to 75% (**+75.0 pp** [+47.8, +88.8]); stacking evidence-validation lifted 75% to 100% (**+25.0 pp** [+11.1, +40.2]); and the same validator, un-stacked, recovered **+45.0 pp** [+28.2, +60.2] of llama-3.1-8b's hallucination gap, with the 55% residual hand-decomposed into failures a self-consistency check structurally cannot reach. The contribution is the measurement discipline: matched guardrails, honest intervals, and nulls reported as results.

---

## 1. Introduction

Agent loops — a model that reasons, calls tools, observes results, and repeats — fail in production for reasons that have little to do with intelligence. A tool returns a transient 503. The model emits a call with the wrong parameter name. It computes the right answer and then narrates *"calling submit_answer…"* without ever calling it. Or it submits a confidently wrong number that raises no error anywhere. The standard engineering response is a stack of *reliability guardrails* — retries, corrective re-prompts, submission prods, answer validators — widely deployed, rarely measured. The question this project answers narrowly and honestly: **for one multi-step tool task, how many percentage points of task completion does each guardrail actually add, with real confidence intervals — and where does it add nothing?**

The framing is deliberate and load-bearing (recorded as decision D1 in the project's decision log): this work *reproduces and measures known primitives*; it invents nothing. The defensible claim is a clean measurement — "this guardrail adds X points, ± this much, on this testbed" — not a novel technique. Two further honesty commitments shape everything below. First, where a failure gap had to be *manufactured* by injecting faults (because the model under test refused to fail naturally), every figure and every claim says so plainly. Second, a measured **null is a result**: two of the experiments below found that a guardrail bought nothing, and those nulls are reported with the same prominence as the wins, because they locate the boundary of the thesis.

That thesis, which emerged across the experiments rather than being assumed: **each mechanical failure class is closed by exactly one matched guardrail, and a mismatched guardrail measurably does nothing.** Its corollary is a capability interaction — the stronger the model, the less any guardrail buys, until (for GLM-4.6 on this task) there is nothing to close at all.

Contributions, all scoped to this testbed:

1. A minimal, fully offline-testable measurement harness: a bare reason→act→observe loop with four independently toggleable guardrails, a deterministic oracle, seeded fault injectors, and proportion statistics with a mechanized "may we claim a result?" gate.
2. Five ablation results with 95% intervals: one injected-gap win (+32.5 pp), one injected-gap null, one natural-gap win (+75 pp) with an in-experiment negative control that nulled, and a best-case/messy-case bracket of an evidence-validation guardrail (+25 pp and +45 pp).
3. A hand-read decomposition of the validator's blind spot: the 55% of a weak model's hallucination gap that a self-consistency check structurally cannot recover, split into named, quantified slices.

## 2. Background and Related Work

The four guardrails reproduced here are established patterns in agent engineering; this project's repository deliberately does not trace them to specific publications, and we decline to invent citations for them. They differ along two axes that turn out to carry all the explanatory weight — *what triggers them* and *what they cost*:

| Guardrail | Fires on | Cost | Failure class it targets |
| --- | --- | --- | --- |
| **Error-recovery** | a *transient* tool error (503-style) | none — the harness retries inside the same step; no model turn | flaky service / transient fault |
| **Retry-nudge** | a *failed* (e.g. malformed) tool call | one model turn (a corrective re-prompt) | the model's own call is wrong |
| **Submit-nudge** | a turn ending in prose with *no submission* | one model turn | right answer, never submitted ("protocol gap") |
| **Validation** | a *submitted-but-inconsistent* answer | one model turn | wrong answer, no error |

The first two fire on tool *errors*; submit-nudge fires on a *missing* terminal call; validation fires on a submitted answer that contradicts the model's own retrieved evidence. That trigger taxonomy is what "matched guardrail" means throughout.

For the statistics we follow standard practice for proportions: the Wilson score interval per arm [Wilson, 1927] and Newcombe's "square-and-add" method (his method 10) for the difference between two independent proportions [Newcombe, 1998]. A completion rate is a proportion, not a normal average; near 0% or 100% with small N — exactly this project's regime — mean ± standard deviation and Wald-style intervals misbehave (they can escape [0, 1] and understate uncertainty), while Wilson stays sane at the edges and Newcombe carries that edge behavior into the difference, which is the number actually reported.

## 3. Methods

### 3.1 The harness

The agent (`agent.py`) is the deliberately bare loop: ask the model what to do next, execute the tool it asks for, feed the result back, repeat, for at most 6 steps. A run ends one of three ways — `submitted` (the model called the terminal tool), `no_submit` (it ended in prose), or `max_steps`. There are **zero reliability mechanisms by default**; each guardrail is an independent opt-in toggle (`recover`, `nudge`, `submit_nudge`, `validate`). Every step of every run is appended to a JSONL trajectory, so failures can be hand-read and classified — that *failure triage* is a first-class method here. Tasks are data, not code paths: a frozen `Scenario` bundles tools, prompts, registry, terminal tool, and ground truth. Guardrails wrap the *loop*, never the task, so the scenario is byte-identical across arms.

### 3.2 Deterministic grading — never an LLM judge

Success is graded by a pure-Python oracle (`oracle.py`): the submitted number is compared, by exact equality, to a ground truth computed independently from the same records (D2). An LLM judge would be self-graded homework — a system from the same class as the one under test, sharing its blind spots and adding noise and sycophancy. Measuring a small between-arm delta needs a fixed ruler.

### 3.3 Fault injection

GLM-4.6 aced the clean task 20/20 (§4.3), so there was no natural gap to measure — the project's pre-registered kill-trigger fired, and the recorded response (D12) was to *inject* faults and disclose it, rather than pretend a natural gap existed. Two deterministic, seeded, non-mutating injectors (`faults.py`) wrap a scenario's lookup tools:

- **Transient 503s** (`with_faults`): each lookup call fails with probability `rate` with a retryable "temporarily unavailable" error. A fresh call re-draws — so any retry can clear it.
- **Malformed-call faults** (`with_malformed_faults`): an "armed" tool rejects its documented parameter with a fixable hint (`400 invalid_argument: … use 'id' instead`). Two load-bearing properties: it is **permanent** (classified non-retryable, so error-recovery structurally cannot touch it) and **sticky** (armed per seed+tool, not re-drawn per call, so a blind identical resend keeps failing and only a genuinely corrected call clears it — otherwise we would measure luck, not correction).

`rate=0` reproduces the clean task exactly. Injected gaps are labeled *injected* on every figure; the fault rate is a published knob, not a hidden thumb on the scale.

### 3.4 Ablation design and statistics

An experimental *arm* is config — a label plus the toggle it switches on. All arms of an experiment run over the same per-trial seeds (`with_faults(seed=i)`), making comparisons **paired** on identical fault patterns; "N" always means the number of *distinct* seeds or trials, never a re-pooling of re-runs (D13/D15). Trials run sequentially, each with a fresh message history, so nothing leaks between them.

Every arm gets a Wilson 95% interval; every non-baseline arm gets a Newcombe 95% interval on its difference from the reference arm; and a coded gate, `excludes_zero`, decides whether a difference may be called a result at all. **A difference whose interval includes zero is reported as a null** — this rule was fixed before any paid run (D7/D16). Models run at temperature 0.7 always (recorded per run); determinism is not faked via temperature 0 — signal comes from N (D5). The binding constraint throughout is the statistics, not the code: N ≥ 20 per arm, sized upward when the expected effect is small. For the two validation experiments, N was chosen by computing the intervals in advance with the project's own `stats.py`: at N=20 the expected ~25 pp effect was knife-edge (a plausible outcome straddles zero), at N=40 it clears zero across the plausible envelope (D22, D23).

Every paid run was gated by a cheap pilot (N≈6–8) with pre-registered routing rules, so a null or a mis-matched testbed was caught for pennies before the full spend. The harness itself is covered by 12 offline, network-free test suites (77 tests; run by CI on every pull request).

### 3.5 The validation guardrail's bright lines

Validation is the one guardrail with an integrity trap: if the checker knows the right answer, the experiment has hidden the answer key inside the agent and forced a fake 100%. The design (D22) avoids this with two bright lines enforced in code: (1) the validator **never reads the scenario's ground truth** — it recomputes the expected total only from the tool results the model itself retrieved *this run*; (2) on a mismatch, the corrective re-prompt names the retrieved components (e.g. "140" and "18") and the rule (add both) but **never states the sum**, so the model still does the arithmetic itself. It is therefore a *self-consistency* check — "does your answer match the evidence you gathered?" — and it **can be fooled**: a wrong-record retrieval yields a self-consistent-but-wrong total the validator must accept and the oracle still fails. That fooling was observed live (§5.5) and is the proof the check is not an answer key. Where it cannot recompute (evidence never retrieved, or a non-numeric submission) it accepts by design rather than guess.

## 4. Experimental Setup

### 4.1 The task

A lookup-then-compute scenario (`scenario.py`): the model must fetch an order record (`get_order` → item total **140**, ship zone WEST), fetch that zone's shipping rate (`get_ship_rate` → **18**) — a *chained* lookup, since the zone comes out of the first result — add them, and call the terminal tool `submit_answer` with the grand total (ground truth **158**). The arithmetic is a single addition on purpose: hard math would manufacture *cognitive* failures, and the thesis is about *mechanical* ones (D3). The answer is captured by a structured terminal tool call, never scraped from prose (D4).

### 4.2 Models

Three open-weight models, all accessed via OpenRouter's OpenAI-compatible API (not self-hosted — an early framing ambition the project explicitly did not pursue): **GLM-4.6** (`z-ai/glm-4.6`, the strong subject), **mistral-nemo** (`mistralai/mistral-nemo`, mid), and **llama-3.1-8b-instruct** (`meta-llama/llama-3.1-8b-instruct`, weak). The weaker two were selected by fit pilots after the strong model refused to fail naturally (§5.3).

### 4.3 Why GLM-4.6's gaps had to be injected

Four independent probes found no natural gap on GLM-4.6: **20/20** on the clean task (S3); self-healed malformed calls (S6, §5.2); and **8/8 then 8/8** on two deliberately hardened task variants (S7) — a 4-lookup chain through 15 look-alike records, then a 5-lookup chain through ~25 records with a near-duplicate-customer distractor, each solved perfectly under a pre-agreed ≥7/8 stop rule (D20). A diagnostic run at injection rate 0.5 (N=20) produced 16/20 = 80%, with all four misses being `max_steps` retry-exhaustion — mechanical and recoverable (D13), confirming injection creates the right *kind* of gap. The five experiments:

| # | Stage | Testbed | Model | N/arm | Arms |
| --- | --- | --- | --- | --- | --- |
| E1 | S4/S5 | **injected** transient 503s, rate 0.6 | GLM-4.6 | 40 | baseline · +error-recovery |
| E2 | S6 | **injected** malformed calls, rate 0.6 | GLM-4.6 | 20 | baseline · +error-recovery · +retry-nudge |
| E3 | S8 | **clean** (natural no-submit gap) | mistral-nemo | 20 | baseline · +retry-nudge · +submit-nudge |
| E4 | S9 | **clean** (natural wrong-answer gap), *stacked* | mistral-nemo | 40 | submit-nudge (ref.) · +validation |
| E5 | S10 | **clean** (natural hallucination gap), *un-stacked* | llama-3.1-8b | 40 | baseline · +validation |

## 5. Results

All rates below carry Wilson 95% intervals; all gaps carry Newcombe 95% intervals; verdicts follow the pre-registered straddles-zero gate. Every number is lifted from the vendored result files in `docs/figures/*-data.json` and the decision log; the companion presenter pack maps each claim to its source file.

**Consolidated results.** (pp = percentage points)

| Exp. | Arm | k/N | Rate | Wilson 95% | Gap vs reference (Newcombe 95%) | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| E1 | baseline | 27/40 | 67.5% | [52.0%, 79.9%] | — | — |
| E1 | +error-recovery | 40/40 | 100% | [91.2%, 100%] | **+32.5 pp** [+17.3, +48.0] | **real** |
| E2 | baseline | 20/20 | 100% | [83.9%, 100%] | — | — |
| E2 | +error-recovery | 20/20 | 100% | [83.9%, 100%] | +0.0 pp [−16.1, +16.1] | **null** |
| E2 | +retry-nudge | 20/20 | 100% | [83.9%, 100%] | +0.0 pp [−16.1, +16.1] | **null** |
| E3 | baseline | 0/20 | 0% | [0%, 16.1%] | — | — |
| E3 | +retry-nudge | 0/20 | 0% | [0%, 16.1%] | +0.0 pp [−16.1, +16.1] | **null** |
| E3 | +submit-nudge | 15/20 | 75% | [53.1%, 88.8%] | **+75.0 pp** [+47.8, +88.8] | **real** |
| E4 | submit-nudge (ref.) | 30/40 | 75% | [59.8%, 85.8%] | — | — |
| E4 | +validation (stacked) | 40/40 | 100% | [91.2%, 100%] | **+25.0 pp** [+11.1, +40.2] | **real** |
| E5 | baseline | 0/40 | 0% | [0%, 8.8%] | — | — |
| E5 | +validation (un-stacked) | 18/40 | 45% | [30.7%, 60.2%] | **+45.0 pp** [+28.2, +60.2] | **real** |

### 5.1 E1 — Error-recovery closes the injected transient-fault gap (+32.5 pp, real)

GLM-4.6, N=40 paired seeds, fault rate 0.6, temperature 0.7. The bare baseline completed **27/40 = 67.5%** [52.0%, 79.9%]; all 13 misses were `max_steps` — the model dutifully re-called the 503'd tool on its own turns until the 6-step budget ran out (retry-exhaustion). With error-recovery — the harness silently retries a *transient* fault inside the same step, spending no model turn — completion rose to **40/40 = 100%** [91.2%, 100%], the harness absorbing **104** injected 503s. Gap closed: **+32.5 pp**, Newcombe [+17.3, +48.0], which clears zero; the Wilson bars also do not overlap. This is a real result by the gate — and an *injected* one: a controlled fault-recovery testbed, stated on the figure itself. Because 100% is a boundary, the honest read of the mechanism arm is its Wilson lower bound (91.2%), not "certainly perfect."

![Gap-closure chart: baseline 67.5% vs +error-recovery 100% on GLM-4.6; gap +32.5 pp, Newcombe 95% CI [+17.3, +48.0]. The gap is INJECTED (controlled fault-recovery testbed); 104 transient 503s were absorbed at the harness.](../figures/gap-closure.png)

### 5.2 E2 — On injected malformed calls, no guardrail beats the baseline (null)

GLM-4.6, N=20 paired seeds, malformed-call rate 0.6. All three arms completed **20/20 = 100%** [83.9%, 100%]. Error-recovery was structurally inert (a permanent error is never retried — the in-experiment control showing the *wrong* guardrail does nothing). Retry-nudge *did* fire — **26** corrective re-prompts — and changed nothing, because the baseline needed no help: trajectory reads show GLM-4.6 treats the `400 … use 'id' instead` hint as an ordinary tool observation and corrects its own call on the very next turn, unaided. Both gaps: **+0.0 pp**, Newcombe [−16.1, +16.1] — straddles zero — **a null, reported as one**. No honest tuning rescues it: the nudge adds neither information (the hint is already in the tool result) nor turn economics (self-correcting and nudge-then-correcting each cost one turn), so raising the fault rate floors both arms equally.

![Malformed-call testbed: baseline, +error-recovery, and +retry-nudge all 100% (20/20) on GLM-4.6; both gaps +0.0 pp, Newcombe 95% CI [−16.1, +16.1] — a null. The gap is INJECTED; retry-nudge spent 26 corrective re-prompts that changed nothing.](../figures/malformed-gap.png)

The null is the finding: **a guardrail earns its keep only where the model can't help itself.** E1's +32.5 pp came specifically from turn-exhaustion, which malformed calls don't cause in this model.

### 5.3 E3 — Submit-nudge closes a weak model's natural no-submit gap (+75 pp, real; the mismatched guardrail nulls in the same run)

Since GLM-4.6 would not fail naturally, the variable flipped: hold the task fixed and *clean* (no injection) and swap in weaker models. Fit pilots (N=8 each, 0/16 combined) exposed a **capability cliff** with two failure modes, neither visible to the existing guardrails: llama-3.1-8b *hallucinates* the final number even with the data in hand, and mistral-nemo computes the right answer (158) but **never calls the terminal tool** — it narrates "calling submit_answer…" and stops. The matched guardrail for the latter is **submit-nudge**: when a turn ends in prose with nothing submitted, re-prompt the model to actually call the tool.

mistral-nemo, N=20, clean, temperature 0.7: **baseline 0/20** [0%, 16.1%] (17 runs stalled without submitting; 3 submitted a wrong 140); **+retry-nudge 0/20** — it fired **zero** times, because a *missing* call is not a *failed* call — a null [−16.1, +16.1] that serves as the in-experiment negative control; **+submit-nudge 15/20 = 75%** [53.1%, 88.8%], firing 15 re-prompts, a gap of **+75.0 pp** [+47.8, +88.8] — clears zero, non-overlapping bars, real. This is the project's first *natural* (un-injected) gap closure, and it shows guardrail specificity in one picture: the wrong guardrail does nothing; the matched one lifts. One disclosed caveat: part of nemo's no-submit behavior is *asking* "shall I submit?", and this one-shot harness ends on prose — so submit-nudge is partly the harness replying "yes, go."

![Weak-model natural gap on mistral-nemo (clean task): baseline 0%, +retry-nudge 0% (null — fired zero times), +submit-nudge 75%; gap +75.0 pp, Newcombe 95% CI [+47.8, +88.8]. The gap is NATURAL (no injection); residual misses are wrong-answer (validation) failures.](../figures/weak-gap.png)

The residual — 5/20 runs submitted **140**, the item total with shipping silently forgotten — is a *wrong answer with no error*, which submit-nudge structurally cannot fix. That residual motivates E4.

### 5.4 E4 — Validation closes the residual wrong-answer gap (+25 pp, real; the ladder reads 0% → 75% → 100%)

A hand-read of all 20 E3 submit-nudge trajectories first established that every one of the 5 wrong `140`s had correctly retrieved *both* inputs (140 and 18) and simply failed to add them — pure arithmetic slip, the cleanest possible validation target (D22). Because nemo's bare baseline is 0% (it never submits), the wrong-answer gap is *masked* until submit-nudge lifts it — so this ablation is **stacked**: both arms carry submit-nudge; validation toggles on top, and the reference arm is submit-nudge, not the bare baseline.

mistral-nemo, N=40, clean: **submit-nudge (reference) 30/40 = 75%** [59.8%, 85.8%] (10 misses, all wrong 140s) vs **+validation 40/40 = 100%** [91.2%, 100%], gap **+25.0 pp** [+11.1, +40.2] — clears zero, real. Validation fired 5 times in the full run; across pilot and full run it fired on **6/6** of the `140`s it ever saw and converted every one into a genuine, model-recomputed 158. The full ladder on this model: **0% (bare) → 75% (+submit-nudge) → 100% (+validation)**. N=40 rather than 20 was chosen *before* spending, because the project's own interval code showed N=20 knife-edge for a ~25 pp effect.

![Stacked validation ablation on mistral-nemo (clean task): submit-nudge 75% vs +validation 100%; gap +25.0 pp, Newcombe 95% CI [+11.1, +40.2]. The gap is NATURAL; validation recomputes from the model's OWN retrieved data — a self-consistency check, not the answer key.](../figures/validation-gap.png)

### 5.5 E5 — The same validator on a messy gap: +45 pp, and the blind spot becomes a number

E4 measured validation on its best case. E5 is the stress test: the same guardrail, byte-for-byte, on llama-3.1-8b, whose natural failure is *hallucination* — it submits made-up numbers (e.g. `1234.56`) and, twice in the pilot, the literal formula string `"item_total_usd + ship_rate"`. Unlike nemo, llama *does* submit unaided, so nothing masks the gap and the ablation is **un-stacked**: bare baseline vs +validation. The N=8 pilot lifted 0/8 → 3/8 and caught the predicted fooling scenario live: one run fetched the wrong zone's rate (12) and validation accepted the self-consistent-but-wrong **152** — which the oracle still failed.

llama-3.1-8b, N=40, clean: **baseline 0/40 = 0%** [0%, 8.8%] (39 of 40 runs submitted — garbage) vs **+validation 18/40 = 45%** [30.7%, 60.2%], gap **+45.0 pp** [+28.2, +60.2] — clears zero, real. Validation fired 20 times; 17 of the 18 wins were genuine fired-and-corrected runs.

The stage's real deliverable is the **decomposition**: every one of the 22 validation-arm misses was hand-read and classified. The 55% of runs validation did not recover is the check's structural blind spot, now quantified:

| Residual slice | Share | Why validation structurally can't touch it |
| --- | --- | --- |
| never retrieved the shipping rate | **35%** (14/40) | nothing to recompute from — the validator accepts by design rather than guess |
| wrong-record retrieval | **10%** (4/40) | self-consistent 152 = 140 + the wrong zone's 12 — the validator *fooled*; the oracle still fails it |
| non-numeric submission | **7.5%** (3/40) | formula strings / junk pass through; the oracle fails them |
| never submitted | **2.5%** (1/40) | nothing to validate |

![Un-stacked validation ablation on llama-3.1-8b (clean task): baseline 0% vs +validation 45%; gap +45.0 pp, Newcombe 95% CI [+28.2, +60.2]. The gap is NATURAL; the 55% residual is UN-VALIDATABLE, hand-decomposed: 35% never-retrieved evidence, 10% wrong-record (validator fooled), 7.5% non-numeric, 2.5% no-submit.](../figures/hallucination-gap.png)

Read together, E4 and E5 bracket the mechanism: **validation fixes consistency failures, never evidence failures.** E4 alone would over-sell the check (100% on a pure-slip gap); E5 calibrates it. The fooled 152s are also the integrity proof: an answer key could not be fooled. One disclosed nuance: the validator anchors on the *first* retrieved value of each field, so one run that fetched 12 first and 18 later was checked against the wrong-evidence total (counted in the 10% row) — a design property left unchanged mid-experiment rather than patched. Separately, llama exposed a latent harness bug — it sometimes emits tool arguments as a JSON *array*, which parses but is not an argument object; the fix (route non-object args down the existing malformed-arguments path) adds no help to any arm and is covered by regression tests.

### 5.6 The capability ladder (no new measurements)

The capstone figure re-plots already-measured numbers as a ladder: the same clean task, three models strong→weak, baseline vs +matched guardrails. Three honesty details are load-bearing. **GLM-4.6 gets no guardrail bar** — no guardrail arm was ever run on its clean task because four probes showed nothing to close; drawing a bar would fabricate a measurement, so an annotation carries the finding (its +32.5 pp win was on the *injected* testbed). **nemo's +100.0 pp gap [+81.7, +100.0] is cross-run** — its 0/20 baseline is the E3 run and its 40/40 stack is the E4 run, two independent samples disclosed as such rather than passed off as one ablation. **llama's bar stops at 45% by design** — the remaining 55% is the measured blind spot. The ladder's claim is therefore *matched guardrails recover the recoverable slice*, not *guardrails fix weak models*. The capstone's data file is derived programmatically from the per-stage result files on every render (one documented hand-typed constant: S3's 20/20), so the summary cannot drift from its sources.

![Capability ladder across GLM-4.6 (100% baseline, no guardrail bar — nothing to close), mistral-nemo (0% → 100% under submit-nudge + validation, +100.0 pp [+81.7, +100.0], a disclosed cross-run gap), and llama-3.1-8b (0% → 45% under validation, +45.0 pp [+28.2, +60.2]; the 55% residual is the measured blind spot).](../figures/capstone-ladder.png)

## 6. Discussion

**The matched-guardrail thesis.** Each failure class was closed by exactly one guardrail, measured under the same gate: transient fault → error-recovery (+32.5 pp, injected); malformed call → retry-nudge (null — the model self-heals); no-submit → submit-nudge (+75 pp, natural); wrong-answer-no-error → validation (+25 pp best case, +45 pp messy case, natural). Specificity was demonstrated *within* experiments, not just asserted: E2 ran error-recovery against a permanent fault it cannot retry (null, structural), and E3 ran retry-nudge against a missing call it cannot see (null, zero fires). A guardrail is not generic robustness; it is a keyed patch for one named failure.

**The boundary is the model's own competence.** The E2 null sharpens E1 rather than undermining it: error-recovery's +32.5 pp came specifically from *turn-exhaustion* — transient faults made the model burn its step budget on manual retries, and a free harness retry rescued exactly that. Malformed calls never exhaust turns on GLM-4.6 (one extra step fixes them), so no guardrail moves the number. Guardrails pay where the model cannot help itself.

**The capability × guardrail interaction.** Holding the task fixed and lowering only model capability turned guardrail payoff from zero (GLM-4.6 — nothing to close) to decisive (+75, +25, +45 pp). The claim is the interaction, not "weak models are bad": a weak-but-tool-capable model needs guardrails a strong one does not, and the *kind* of guardrail it needs depends on *how* it fails (nemo needed a protocol prod; llama needed an evidence check).

**What validation is and is not.** The bracket (100% of a pure-slip gap; 45% of a hallucination gap) plus the decomposition gives a deployable mental model: a self-consistency check converts *inconsistency* failures into successes, is inert on *missing-evidence* failures, and is fooled by *wrong-evidence* failures — so its value depends on the failure mix, which a hand-read pilot can measure before committing to the mechanism.

## 7. Limitations and Threats to Validity

- **The GLM-4.6 gaps are manufactured.** E1 and E2 measure recovery of *injected* faults at a chosen rate (0.6) — a controlled testbed, disclosed on every figure, not evidence that GLM-4.6 fails this way in the wild. On this task it demonstrably does not (20/20 clean; 8/8 twice on hardened variants).
- **One task family.** Every number comes from one lookup-then-compute scenario (plus hardened variants used only for the no-natural-gap probes). External validity is deliberately narrow; every claim is scoped to this testbed.
- **Small N, wide intervals.** N is 20–40 per arm; a 40/40 arm's honest reading is its Wilson lower bound (91.2%), not certainty. The intervals are carried everywhere precisely because they are wide.
- **Stochastic, third-party-hosted models.** Temperature 0.7 with per-trial seeds governs the *fault patterns*, not the model; exact replay of live numbers is not possible, and OpenRouter routing may change. The analysis pipeline, by contrast, is fully reproducible offline from the vendored result files. The models are OpenRouter-hosted, not self-hosted, despite the project's early framing.
- **Submit-nudge partially answers the model.** Part of nemo's no-submit behavior is asking permission; the nudge is partly the harness saying "yes." Disclosed on the figure; the failure and the lift are still real.
- **Validator design limits.** Accept-by-design on missing evidence and non-numeric submissions; first-evidence anchoring; foolable by wrong-record retrieval. These are quantified (E5) rather than fixed, and they are what keeps the check honest.
- **The nemo +100.0 pp capstone gap is cross-run** (E3 baseline vs E4 stack), statistically sound for independent proportions but not a single paired ablation; disclosed on the figure.
- **Costs were not systematically recorded.** Token/dollar totals for the main ablations were not logged as results; the repository records only qualitative spend notes and one pilot's token counts. No cost claims are made here.

## 8. Conclusion

Four reproduced guardrails, five measured deltas, two honest nulls, and one decomposed blind spot — each number carrying a Wilson interval, each gap a Newcombe interval, each claim gated by a pre-registered straddles-zero rule. The project stops on purpose: the story is bracketed at both ends — the strongest model tested needs no guardrails at all, and the weakest model's failures are partly beyond what any self-consistency guardrail can reach. Two roads not taken are recorded as future projects, not pending work: a live capability-ladder sweep across more models, and a genuinely self-hosted endpoint. Within its narrow scope, the result is a defensible answer to a question usually hand-waved: *what does each guardrail actually buy?* — here, exactly +32.5, +0.0, +75.0, +25.0, and +45.0 percentage points, ± honest intervals, on the testbeds stated.

## Provenance and Reproducibility

Every statistic in this paper is lifted verbatim from the repository's vendored result files (`docs/figures/*-data.json` — the same files the committed figures render from, via `uv run chart.py`, no API calls) or from the decision log (`docs/DECISIONS.md`, entries D12–D24) for pilot results, trajectory hand-reads, and the E5 decomposition. A claim-by-claim mapping (claim → number → source file) is in the companion presenter pack (`forge-gap-presenter-pack.md`). The harness, injectors, oracle, and statistics are covered by 12 offline test suites (77 tests) run by CI.

## References

The four guardrail primitives (error-recovery/retry, corrective re-prompting, submit prodding, output validation) are reproduced as established practice in LLM-agent engineering; the project does not trace them to specific publications, and no citations are invented for them. The statistical methods are standard:

- Wilson, E. B. (1927). Probable inference, the law of succession, and statistical inference. *Journal of the American Statistical Association*, 22(158), 209–212. (The Wilson score interval.)
- Newcombe, R. G. (1998). Interval estimation for the difference between independent proportions: comparison of eleven methods. *Statistics in Medicine*, 17(8), 873–890. (Method 10, the "square-and-add" interval used for all between-arm gaps.)

Model and API documentation recorded in the repository README: the OpenRouter quickstart and tool-calling guides, and the GLM-4.6 model page (openrouter.ai).
