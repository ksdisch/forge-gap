# Matched Guardrails: Reproducing and Measuring Four Reliability Primitives for LLM Tool-Use Agents

> **This is a plain-English rewrite.** It mirrors the original paper 1:1 — same headings,
> same paragraphs, same order. Nothing is summarized, merged, dropped, or reordered; only
> the language changes. Tables are reproduced exactly as they appear in the original, each
> followed by an italic *"In plain words"* line; figures keep their original images, with
> the caption text rewritten. The references section is carried through untouched.
>
> **Original paper:** *Matched Guardrails: Reproducing and Measuring Four Reliability Primitives for LLM Tool-Use Agents*
> **Author:** Kyle Disch
> **Source:** `docs/paper/forge-gap-paper.md` (branch `docs/paper-and-presenter-pack`, open PR [#22](https://github.com/ksdisch/forge-gap/pull/22))
> **Rewrite generated:** 2026-07-27

**The forge-gap experiments** · Kyle Disch · 2026-07-08

---

## Abstract

Large language model agents fail at multi-step tool tasks for mechanical reasons — a tool that flakes out, a badly formed request, an answer worked out but never actually submitted, a wrong number submitted with nothing flagging an error. Engineers bolt on reliability safeguards (automatic retries, corrective re-prompts, output checkers) without ever measuring what each one is worth. We re-implement four such safeguards — error-recovery, retry-nudge, submit-nudge, and evidence-validation, all of them established practice rather than anything we invented — and measure each one against the single kind of failure it is meant to address, on a fixed look-something-up-then-calculate task, graded by a fixed program rather than by another model, with a plausible range around each condition's success rate, a plausible range around every difference between conditions, and a rule fixed in advance that any difference whose range includes zero gets reported as no effect. On GLM-4.6, which shows no natural weakness, we had to inject failures ourselves (and we label them as manufactured throughout): having the test harness handle temporary tool errors closed an injected gap worth **32.5 percentage points** (plausible range [+17.3, +48.0]), while the retry-nudge produced **no effect at all** on injected badly formed requests (+0.0 points, range [−16.1, +16.1]) — the model fixes those itself. On weaker models the weaknesses are natural: the submit-nudge lifted mistral-nemo from 0% to 75% (**+75.0 points**, range [+47.8, +88.8]); adding evidence-validation on top of that lifted 75% to 100% (**+25.0 points**, range [+11.1, +40.2]); and the same checker, used on its own, recovered **+45.0 points** (range [+28.2, +60.2]) of llama-3.1-8b's tendency to make numbers up, with the remaining 55% broken down by hand into failures that a consistency check structurally cannot reach. What this contributes is the measurement discipline: safeguards matched to specific failures, honest ranges, and no-effect results reported as findings.

---

## 1. Introduction

Agent loops — a model that reasons, calls a tool, looks at the result, and repeats — fail in production for reasons that have little to do with intelligence. A tool returns a temporary "service unavailable." The model sends a request with the wrong parameter name. It works out the right answer and then narrates *"calling submit_answer…"* without ever making the call. Or it submits a confidently wrong number that triggers no error anywhere. The standard engineering response is a stack of *reliability safeguards* — retries, corrective re-prompts, prods to submit, answer checkers — widely deployed and rarely measured. The question this project answers narrowly and honestly: **on one multi-step tool task, how many percentage points of task completion does each safeguard actually add, with real plausible ranges attached — and where does it add nothing at all?**

The framing is deliberate and it carries weight (it is recorded as decision D1 in the project's decision log): this work *re-implements and measures known techniques*; it invents nothing. What we can defend is a clean measurement — "this safeguard adds X points, give or take this much, on this test setup" — not a new technique. Two further honesty commitments shape everything below. First, wherever a failure gap had to be *manufactured* by injecting faults, because the model being tested refused to fail on its own, every figure and every claim says so plainly. Second, a measured **no-effect result is a result**: two of the experiments below found that a safeguard bought nothing, and those are reported just as prominently as the wins, because they mark the boundary of the thesis.

That thesis emerged across the experiments rather than being assumed at the start: **each mechanical kind of failure is closed by exactly one matching safeguard, and a mismatched safeguard measurably does nothing.** Its corollary is an interaction with model capability — the stronger the model, the less any safeguard buys, until (for GLM-4.6 on this task) there is nothing left to close at all.

Contributions, all limited to this test setup:

1. A minimal measurement harness that can be fully tested offline: a bare reason-act-observe loop with four independently switchable safeguards, a fixed grading program, seeded fault injectors, and percentage statistics with an automated "are we allowed to claim a result?" check.
2. Five comparison results with plausible ranges attached: one win on an injected gap (+32.5 points), one no-effect result on an injected gap, one win on a natural gap (+75 points) with a built-in control condition that produced no effect, and a best-case/worst-case bracket around an evidence-checking safeguard (+25 points and +45 points).
3. A hand-read breakdown of the checker's blind spot: the 55% of a weak model's made-up-answer failures that a consistency check structurally cannot recover, split into named slices with numbers attached.

## 2. Background and Related Work

The four safeguards re-implemented here are established patterns in agent engineering; this project's repository deliberately does not trace them to specific publications, and we decline to invent citations for them. They differ along two axes that turn out to carry all the explanatory weight — *what sets them off* and *what they cost*:

| Guardrail | Fires on | Cost | Failure class it targets |
| --- | --- | --- | --- |
| **Error-recovery** | a *transient* tool error (503-style) | none — the harness retries inside the same step; no model turn | flaky service / transient fault |
| **Retry-nudge** | a *failed* (e.g. malformed) tool call | one model turn (a corrective re-prompt) | the model's own call is wrong |
| **Submit-nudge** | a turn ending in prose with *no submission* | one model turn | right answer, never submitted ("protocol gap") |
| **Validation** | a *submitted-but-inconsistent* answer | one model turn | wrong answer, no error |

*In plain words: a summary of the four safeguards. Reading each row: what event triggers it, what it costs to run (only the first is free, because the harness handles it without going back to the model), and which specific kind of failure it exists to fix. The point of the table is that each one is keyed to a different trigger.*

The first two are set off by tool *errors*; the submit-nudge is set off by a *missing* final call; validation is set off by a submitted answer that contradicts the evidence the model itself gathered. That taxonomy of triggers is what "matched safeguard" means throughout this paper.

For the statistics we follow standard practice for percentages: the Wilson score interval for each condition [Wilson, 1927] and Newcombe's "square and add" recipe (his method 10) for the difference between two independent percentages [Newcombe, 1998]. A completion rate is a percentage, not an ordinary average; close to 0% or 100% with a small number of trials — which is exactly this project's situation — the familiar mean-plus-or-minus-standard-deviation approach misbehaves, since it can produce ranges that extend below 0% or above 100% and it understates how uncertain the number really is. Wilson stays sensible at those edges, and Newcombe carries that good behaviour through into the difference, which is the number we actually report.

## 3. Methods

### 3.1 The harness

The agent (`agent.py`) is the deliberately bare loop: ask the model what to do next, run whichever tool it asks for, feed the result back, and repeat, for at most 6 steps. A run ends in one of three ways — `submitted` (the model called the final tool), `no_submit` (it ended by writing prose instead), or `max_steps` (it ran out of budget). There are **no reliability mechanisms at all by default**; each safeguard is an independent opt-in switch (`recover`, `nudge`, `submit_nudge`, `validate`). Every step of every run is written out to a transcript file, so failures can be read by hand and classified — that *failure triage* is a first-class method here, not an afterthought. Tasks are treated as data rather than as branches in the code: a frozen `Scenario` bundles together the tools, prompts, registry, final tool, and correct answer. Safeguards wrap the *loop* and never the task, so the scenario is byte-for-byte identical across every condition.

### 3.2 Deterministic grading — never an LLM judge

Success is graded by a plain Python program (`oracle.py`): the submitted number is compared, by exact equality, against a correct answer worked out independently from the same records (D2). Using a language model as the judge would be marking your own homework — a system from the same family as the one being tested, sharing its blind spots and adding both noise and a tendency to agree with whatever it is shown. Measuring a small difference between two conditions requires a ruler that does not move.

### 3.3 Fault injection

GLM-4.6 aced the clean task 20 times out of 20 (§4.3), so there was no natural weakness to measure — the project's pre-registered abort trigger fired, and the recorded response (D12) was to *inject* faults and disclose that we had done so, rather than pretend a natural gap existed. Two predictable, seeded injectors that leave the underlying task untouched (`faults.py`) wrap a scenario's lookup tools:

- **Temporary service errors** (`with_faults`): each lookup call fails with a given probability, returning a retryable "temporarily unavailable" error. A fresh call rolls the dice again — so any retry can clear it.
- **Badly formed request faults** (`with_malformed_faults`): an "armed" tool rejects the parameter its own documentation specifies, returning a fixable hint (`400 invalid_argument: … use 'id' instead`). Two properties carry weight here: the fault is **permanent** (classified as not retryable, so error-recovery structurally cannot touch it) and **sticky** (armed once per seed and tool rather than re-rolled on every call, so blindly resending the identical request keeps failing and only a genuinely corrected request gets through — otherwise we would be measuring luck rather than correction).

Setting the fault rate to zero reproduces the clean task exactly. Injected gaps are labelled *injected* on every figure; the fault rate is a published dial, not a hidden thumb on the scale.

### 3.4 Ablation design and statistics

An experimental *condition* is just configuration — a label plus the switch it turns on. Every condition within an experiment runs over the same per-trial seeds (`with_faults(seed=i)`), which makes the comparisons **paired** on identical fault patterns; "N" always means the number of *distinct* seeds or trials, never the same runs pooled together twice (D13/D15). Trials run one after another, each with a fresh conversation history, so nothing leaks between them.

Every condition gets a Wilson plausible range; every non-baseline condition gets a Newcombe range around its difference from the reference condition; and a coded check, `excludes_zero`, decides whether a difference may be called a result at all. **A difference whose range includes zero is reported as no effect** — this rule was fixed before any paid run took place (D7/D16). Models always run at temperature 0.7, recorded on every run; we do not fake determinism by setting the temperature to zero — the signal comes from the number of trials instead (D5). The binding constraint throughout is the statistics, not the code: at least 20 trials per condition, sized upward when the expected effect is small. For the two validation experiments the trial count was chosen by computing the ranges in advance using the project's own `stats.py`: at 20 trials an expected effect of around 25 points sat right on the knife edge (a plausible outcome would straddle zero), while at 40 trials it clears zero across the whole plausible envelope (D22, D23).

Every paid run was gated behind a cheap pilot of roughly 6 to 8 trials, with routing rules registered in advance, so a no-effect result or a badly matched test setup would be caught for pennies before the full spend. The harness itself is covered by 12 offline, network-free test suites (77 tests, run automatically on every pull request).

### 3.5 The validation guardrail's bright lines

Validation is the one safeguard with an integrity trap built into it: if the checker knows the right answer, then the experiment has hidden the answer key inside the agent and manufactured a fake 100%. The design (D22) avoids this with two bright lines enforced in code: (1) the checker **never looks at the scenario's correct answer** — it recomputes the expected total using only the tool results the model itself retrieved *during this run*; and (2) when there is a mismatch, the corrective re-prompt names the retrieved components (for example "140" and "18") and the rule (add them together) but **never states the sum**, so the model still has to do the arithmetic itself. It is therefore a *consistency* check — "does your answer match the evidence you gathered?" — and it **can be fooled**: retrieving the wrong record produces a total that is self-consistent but wrong, which the checker has to accept and the grading program still marks as a failure. We observed that fooling happen live (§5.5), and it is the proof that the check is not an answer key. Where it cannot recompute anything — because the evidence was never retrieved, or because the submission was not a number — it accepts by design rather than guessing.

## 4. Experimental Setup

### 4.1 The task

A look-up-then-calculate scenario (`scenario.py`): the model has to fetch an order record (`get_order`, giving an item total of **140** and a shipping zone of WEST), then fetch that zone's shipping rate (`get_ship_rate`, giving **18**) — a *chained* lookup, since the zone only becomes known from the first result — add the two together, and call the final tool `submit_answer` with the grand total (the correct answer being **158**). The arithmetic is a single addition on purpose: difficult maths would manufacture *thinking* failures, and this thesis is about *mechanical* ones (D3). The answer is captured through a structured final tool call, never scraped out of the model's prose (D4).

### 4.2 Models

Three open-weight models, all reached through OpenRouter's OpenAI-compatible interface rather than run on our own hardware — self-hosting was an early framing ambition the project explicitly did not pursue: **GLM-4.6** (`z-ai/glm-4.6`, the strong subject), **mistral-nemo** (`mistralai/mistral-nemo`, middling), and **llama-3.1-8b-instruct** (`meta-llama/llama-3.1-8b-instruct`, weak). The two weaker ones were picked by fit pilots after the strong model refused to fail on its own (§5.3).

### 4.3 Why GLM-4.6's gaps had to be injected

Four separate probes found no natural weakness in GLM-4.6: **20 out of 20** on the clean task (stage S3); it fixed badly formed requests by itself (stage S6, §5.2); and **8 out of 8, then 8 out of 8 again** on two deliberately hardened versions of the task (stage S7) — first a 4-lookup chain through 15 similar-looking records, then a 5-lookup chain through roughly 25 records including a near-duplicate customer designed to mislead — each solved perfectly under a stopping rule of at least 7 out of 8 agreed in advance (D20). A diagnostic run with faults injected at a rate of 0.5 across 20 trials produced 16 out of 20, or 80%, with all four misses being cases where the model ran out of steps while retrying — mechanical and recoverable (D13), confirming that injection creates the right *kind* of weakness. The five experiments:

| # | Stage | Testbed | Model | N/arm | Arms |
| --- | --- | --- | --- | --- | --- |
| E1 | S4/S5 | **injected** transient 503s, rate 0.6 | GLM-4.6 | 40 | baseline · +error-recovery |
| E2 | S6 | **injected** malformed calls, rate 0.6 | GLM-4.6 | 20 | baseline · +error-recovery · +retry-nudge |
| E3 | S8 | **clean** (natural no-submit gap) | mistral-nemo | 20 | baseline · +retry-nudge · +submit-nudge |
| E4 | S9 | **clean** (natural wrong-answer gap), *stacked* | mistral-nemo | 40 | submit-nudge (ref.) · +validation |
| E5 | S10 | **clean** (natural hallucination gap), *un-stacked* | llama-3.1-8b | 40 | baseline · +validation |

*In plain words: the five experiments at a glance. The "testbed" column marks whether the weakness being measured was one we injected ourselves or one the model showed naturally; the last column lists which conditions were compared against each other. The first two experiments use the strong model with manufactured faults, and the last three use weaker models that fail on their own.*

## 5. Results

Every rate below carries a Wilson plausible range; every gap carries a Newcombe plausible range; and verdicts follow the straddles-zero rule registered in advance. Every number is lifted from the stored result files in `docs/figures/*-data.json` and from the decision log; the companion presenter pack maps each claim back to its source file.

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

*In plain words: every measurement in the paper in one place. For each experiment, the baseline row shows how often the task succeeded with no safeguard, and the rows beneath show what each safeguard changed. The second-to-last column is the size of that change with its plausible range, and the last column says whether the range excluded zero — "real" if it did, "null" if it didn't. Three of the five safeguards produced a real gain and two changed nothing.*

### 5.1 E1 — Error-recovery closes the injected transient-fault gap (+32.5 pp, real)

GLM-4.6, 40 paired seeds, fault rate 0.6, temperature 0.7. The bare baseline completed **27 out of 40, or 67.5%** [52.0%, 79.9%]; all 13 misses were cases of running out of steps — the model dutifully kept re-calling the failing tool on its own turns until its 6-step budget ran out. With error-recovery switched on — where the harness quietly retries a *temporary* fault within the same step, spending no model turn at all — completion rose to **40 out of 40, or 100%** [91.2%, 100%], with the harness absorbing **104** injected service errors. The gap closed is **+32.5 points**, Newcombe range [+17.3, +48.0], which clears zero; the Wilson ranges for the two conditions also do not overlap. This is a real result by our rule — and an *injected* one: a controlled fault-recovery test setup, stated on the figure itself. Because 100% is a boundary, the honest reading of the safeguard condition is its Wilson lower bound of 91.2%, not "certainly perfect."

![Gap-closure chart: on GLM-4.6, the bare loop finished 67.5% of runs while the version that retries temporary tool errors finished 100% — a gain of 32.5 percentage points, plausible range [+17.3, +48.0]. This weakness was INJECTED by us (a controlled fault-recovery setup); the harness absorbed 104 temporary service errors.](../figures/gap-closure.png)

### 5.2 E2 — On injected malformed calls, no guardrail beats the baseline (null)

GLM-4.6, 20 paired seeds, badly-formed-request rate 0.6. All three conditions completed **20 out of 20, or 100%** [83.9%, 100%]. Error-recovery was structurally inert, because a permanent error is never retried — this is the built-in control showing that the *wrong* safeguard does nothing. The retry-nudge *did* fire — **26** corrective re-prompts — and changed nothing, because the baseline needed no help in the first place: reading the transcripts shows that GLM-4.6 treats the `400 … use 'id' instead` hint as an ordinary tool result and corrects its own request on the very next turn, unaided. Both gaps come to **+0.0 points**, Newcombe range [−16.1, +16.1] — straddling zero — **a no-effect result, reported as one**. No honest tuning rescues it: the nudge adds neither new information (the hint is already sitting in the tool result) nor any saving in turns (correcting itself and being nudged into correcting each cost exactly one turn), so raising the fault rate simply pushes both conditions to the floor together.

![Badly-formed-request setup: the bare loop, the version with error-recovery, and the version with the retry-nudge all finished 100% of runs (20 out of 20) on GLM-4.6; both gaps are 0.0 percentage points with a plausible range of [−16.1, +16.1] — no effect. This weakness was INJECTED; the retry-nudge spent 26 corrective re-prompts that changed nothing.](../figures/malformed-gap.png)

The no-effect result is itself the finding: **a safeguard only earns its keep where the model cannot help itself.** The 32.5-point gain in the first experiment came specifically from running out of turns, which badly formed requests do not cause in this model.

### 5.3 E3 — Submit-nudge closes a weak model's natural no-submit gap (+75 pp, real; the mismatched guardrail nulls in the same run)

Since GLM-4.6 would not fail on its own, we flipped the variable: hold the task fixed and *clean*, with no injected faults, and swap in weaker models instead. Fit pilots of 8 trials each — 0 successes out of 16 combined — exposed a **capability cliff** with two distinct failure modes, neither of which the existing safeguards could see: llama-3.1-8b *makes up* the final number even with the data right in front of it, while mistral-nemo works out the right answer (158) but **never calls the final tool** — it narrates "calling submit_answer…" and then stops. The matching safeguard for the second problem is the **submit-nudge**: when a turn ends in prose with nothing submitted, re-prompt the model to actually make the call.

mistral-nemo, 20 trials, clean task, temperature 0.7: the **baseline scored 0 out of 20** [0%, 16.1%] (17 runs stalled without submitting anything; 3 submitted a wrong answer of 140); **the retry-nudge scored 0 out of 20** — it fired **zero** times, because a *missing* call is not a *failed* call — a no-effect result [−16.1, +16.1] that serves as the built-in negative control; and **the submit-nudge scored 15 out of 20, or 75%** [53.1%, 88.8%], firing 15 re-prompts, for a gap of **+75.0 points** [+47.8, +88.8] — clearing zero, with non-overlapping ranges, a real result. This is the project's first closure of a *natural* (un-injected) weakness, and it demonstrates safeguard specificity in a single picture: the wrong safeguard does nothing while the matching one lifts dramatically. One disclosed caveat: part of nemo's failure to submit is that it *asks* "shall I submit?", and this single-shot harness ends whenever the model produces prose — so the submit-nudge is partly just the harness replying "yes, go ahead."

![A weak model's natural weakness on mistral-nemo with the clean task: the bare loop finished 0% of runs, the retry-nudge also 0% (no effect — it never fired once), and the submit-nudge 75%; a gain of 75.0 percentage points, plausible range [+47.8, +88.8]. This weakness is NATURAL, with nothing injected; the remaining misses are wrong-answer failures that validation targets.](../figures/weak-gap.png)

What remains — 5 of the 20 runs submitted **140**, the item total with the shipping quietly forgotten — is a *wrong answer that raises no error*, which the submit-nudge structurally cannot fix. That remainder is what motivates the next experiment.

### 5.4 E4 — Validation closes the residual wrong-answer gap (+25 pp, real; the ladder reads 0% → 75% → 100%)

Reading all 20 submit-nudge transcripts from the previous experiment by hand first established that every one of the 5 wrong 140s had correctly retrieved *both* inputs (140 and 18) and had simply failed to add them together — a pure arithmetic slip, which is the cleanest possible target for validation (D22). Because nemo's bare baseline sits at 0%, since it never submits anything, the wrong-answer weakness is *hidden* until the submit-nudge exposes it — so this comparison is **stacked**: both conditions carry the submit-nudge, validation is switched on top of it, and the reference condition is the submit-nudge rather than the bare baseline.

mistral-nemo, 40 trials, clean task: the **submit-nudge reference scored 30 out of 40, or 75%** [59.8%, 85.8%] (with all 10 misses being wrong 140s), against **validation switched on scoring 40 out of 40, or 100%** [91.2%, 100%], a gap of **+25.0 points** [+11.1, +40.2] — clearing zero, a real result. Validation fired 5 times during the full run; across the pilot and the full run together it fired on **6 out of the 6** wrong 140s it ever encountered and converted every single one into a genuine 158 that the model recomputed itself. The full ladder on this model reads: **0% bare → 75% with the submit-nudge → 100% with validation added**. We chose 40 trials rather than 20 *before* spending anything, because the project's own interval code showed that 20 would sit on a knife edge for an effect of around 25 points.

![Stacked validation comparison on mistral-nemo with the clean task: the submit-nudge alone finished 75% of runs against 100% with validation added; a gain of 25.0 percentage points, plausible range [+11.1, +40.2]. This weakness is NATURAL; validation recomputes the answer from the model's OWN retrieved data — a consistency check, not the answer key.](../figures/validation-gap.png)

### 5.5 E5 — The same validator on a messy gap: +45 pp, and the blind spot becomes a number

The previous experiment measured validation on its best case. This one is the stress test: the same safeguard, byte for byte, applied to llama-3.1-8b, whose natural failure is *making things up* — it submits invented numbers (for instance `1234.56`) and, twice during the pilot, the literal formula text `"item_total_usd + ship_rate"`. Unlike nemo, llama *does* submit without prompting, so nothing hides the weakness and the comparison is **un-stacked**: bare baseline against validation switched on. The 8-trial pilot lifted 0 out of 8 to 3 out of 8, and caught the predicted fooling scenario live: one run fetched the wrong zone's rate (12) and validation accepted the resulting self-consistent but wrong total of **152** — which the grading program still failed.

llama-3.1-8b, 40 trials, clean task: the **baseline scored 0 out of 40, or 0%** [0%, 8.8%], with 39 of the 40 runs submitting something, just garbage, against **validation switched on scoring 18 out of 40, or 45%** [30.7%, 60.2%], a gap of **+45.0 points** [+28.2, +60.2] — clearing zero, a real result. Validation fired 20 times, and 17 of the 18 successes were genuine cases where it fired and the model then corrected itself.

The real deliverable of this stage is the **breakdown**: every one of the 22 misses in the validation condition was read by hand and classified. The 55% of runs that validation did not recover is the check's structural blind spot, now quantified:

| Residual slice | Share | Why validation structurally can't touch it |
| --- | --- | --- |
| never retrieved the shipping rate | **35%** (14/40) | nothing to recompute from — the validator accepts by design rather than guess |
| wrong-record retrieval | **10%** (4/40) | self-consistent 152 = 140 + the wrong zone's 12 — the validator *fooled*; the oracle still fails it |
| non-numeric submission | **7.5%** (3/40) | formula strings / junk pass through; the oracle fails them |
| never submitted | **2.5%** (1/40) | nothing to validate |

*In plain words: the 55% of runs validation could not save, broken into four named causes with the share of runs each accounts for. The largest by far is the model never fetching the shipping rate at all — with no evidence gathered there is nothing for a consistency check to check against. Together these four rows explain exactly why the safeguard tops out at 45% rather than 100%.*

![Un-stacked validation comparison on llama-3.1-8b with the clean task: the bare loop finished 0% of runs against 45% with validation; a gain of 45.0 percentage points, plausible range [+28.2, +60.2]. This weakness is NATURAL; the remaining 55% is BEYOND WHAT VALIDATION CAN CHECK, broken down by hand into 35% where the evidence was never fetched, 10% where the wrong record was fetched and the checker was fooled, 7.5% where the submission was not a number, and 2.5% where nothing was submitted.](../figures/hallucination-gap.png)

Read together, these last two experiments bracket the mechanism: **validation fixes consistency failures and never evidence failures.** The first one alone would oversell the check, since it hits 100% on a pure-slip weakness; the second calibrates it. The fooled 152s are also the integrity proof: an answer key could not have been fooled. One nuance we disclose: the checker anchors on the *first* retrieved value for each field, so one run that fetched 12 first and 18 later was checked against a total built from the wrong evidence (counted in the 10% row) — a design property we left unchanged mid-experiment rather than patching. Separately, llama exposed a latent bug in the harness: it sometimes sends tool arguments as a JSON *array*, which parses successfully but is not an argument object; the fix (routing non-object arguments down the existing badly-formed-arguments path) gives no advantage to any condition and is covered by regression tests.

### 5.6 The capability ladder (no new measurements)

The summary figure re-plots numbers already measured as a ladder: the same clean task, three models from strong to weak, bare baseline against matched safeguards. Three honesty details carry weight. **GLM-4.6 gets no safeguard bar** — no safeguard condition was ever run on its clean task, because four probes showed there was nothing to close; drawing a bar would fabricate a measurement, so an annotation carries the finding instead (its 32.5-point win came on the *injected* setup). **nemo's +100.0-point gap, range [+81.7, +100.0], spans two separate runs** — its 0-out-of-20 baseline comes from one experiment and its 40-out-of-40 stacked result from another, two independent samples disclosed as such rather than passed off as a single comparison. **llama's bar stops at 45% by design** — the remaining 55% is the measured blind spot. The ladder's claim is therefore *matched safeguards recover the recoverable slice*, not *safeguards fix weak models*. The summary figure's data file is derived automatically from the per-stage result files every time it is rendered (with one documented hand-typed constant, stage S3's 20 out of 20), so the summary cannot drift away from its sources.

![Capability ladder across three models on the same clean task: GLM-4.6 finishes 100% of runs with no safeguard bar drawn, because four probes found nothing to close; mistral-nemo goes from 0% to 100% once the submit-nudge and validation are stacked, a gain of 100.0 percentage points with range [+81.7, +100.0], disclosed as spanning two separate runs; and llama-3.1-8b goes from 0% to 45% under validation, a gain of 45.0 points with range [+28.2, +60.2], where the remaining 55% is the measured blind spot.](../figures/capstone-ladder.png)

## 6. Discussion

**The matched-safeguard thesis.** Each kind of failure was closed by exactly one safeguard, measured under the same rule: a temporary fault is closed by error-recovery (+32.5 points, injected); a badly formed request by the retry-nudge (no effect — the model heals itself); a failure to submit by the submit-nudge (+75 points, natural); and a wrong answer that raises no error by validation (+25 points in the best case, +45 points in the messy case, both natural). Specificity was demonstrated *inside* the experiments rather than merely asserted: one experiment ran error-recovery against a permanent fault it cannot retry (no effect, structurally), and another ran the retry-nudge against a missing call it cannot even see (no effect, zero firings). A safeguard is not general robustness; it is a patch cut to fit one named failure.

**The boundary is the model's own competence.** The no-effect result sharpens the win rather than undermining it: error-recovery's 32.5 points came specifically from *running out of turns* — temporary faults made the model burn its step budget on manual retries, and a free retry inside the harness rescued exactly that. Badly formed requests never exhaust turns on GLM-4.6, since one extra step fixes them, so no safeguard moves the number at all. Safeguards pay off where the model cannot help itself.

**How capability and safeguards interact.** Holding the task fixed and lowering only the model's capability turned safeguard payoff from zero (GLM-4.6, with nothing to close) into decisive gains of +75, +25 and +45 points. The claim is about that interaction, not that "weak models are bad": a weak but tool-capable model needs safeguards that a strong one does not, and *which* safeguard it needs depends on *how* it fails — nemo needed a prod to follow the protocol, while llama needed its evidence checked.

**What validation is and is not.** The bracket — 100% of a pure-slip weakness, 45% of a making-things-up weakness — plus the breakdown gives a mental model you can actually deploy against: a consistency check turns *inconsistency* failures into successes, does nothing at all about *missing-evidence* failures, and is fooled outright by *wrong-evidence* failures. So its value depends entirely on the mix of failures you are facing, which a hand-read pilot can measure before you commit to the mechanism.

## 7. Limitations and Threats to Validity

- **The GLM-4.6 gaps are manufactured.** The first two experiments measure recovery from faults we *injected* at a rate we chose (0.6) — a controlled setup, disclosed on every figure, and not evidence that GLM-4.6 fails this way in the real world. On this task it demonstrably does not (20 out of 20 on the clean version; 8 out of 8 twice on hardened variants).
- **One task family.** Every number comes from a single look-up-then-calculate scenario, plus the hardened variants used only for the no-natural-weakness probes. How far this generalizes is deliberately narrow, and every claim is scoped to this setup.
- **Few trials, wide ranges.** There are 20 to 40 trials per condition; the honest reading of a 40-out-of-40 condition is its Wilson lower bound of 91.2%, not certainty. The ranges are carried everywhere precisely because they are wide.
- **Random, third-party-hosted models.** Temperature 0.7 with per-trial seeds controls the *fault patterns*, not the model, so replaying the exact live numbers is not possible, and OpenRouter's routing may change underneath us. The analysis pipeline, by contrast, is fully reproducible offline from the stored result files. The models are hosted by OpenRouter rather than run on our own hardware, despite the project's early framing.
- **The submit-nudge partly answers for the model.** Part of nemo's failure to submit is that it asks permission; the nudge is partly the harness saying "yes." This is disclosed on the figure, and both the failure and the lift are still real.
- **Limits of the checker's design.** It accepts by design when evidence is missing or the submission is not a number; it anchors on the first piece of evidence it sees; and it can be fooled by retrieval of the wrong record. These are quantified in the fifth experiment rather than fixed, and they are exactly what keeps the check honest.
- **The +100.0-point ladder gap for nemo spans two runs** (one experiment's baseline against another's stacked condition), which is statistically sound for independent percentages but is not a single paired comparison; this is disclosed on the figure.
- **Costs were not recorded systematically.** Token and dollar totals for the main comparisons were never logged as results; the repository records only qualitative notes on spending plus one pilot's token counts. No cost claims are made here.

## 8. Conclusion

Four re-implemented safeguards, five measured differences, two honest no-effect results, and one decomposed blind spot — each number carrying a plausible range for its own rate, each gap carrying a plausible range for the difference, and each claim gated by a straddles-zero rule fixed in advance. The project stops on purpose: the story is bracketed at both ends — the strongest model tested needs no safeguards at all, and the weakest model's failures lie partly beyond what any consistency check can reach. Two roads not taken are recorded as future projects rather than unfinished work: a live capability sweep across more models, and a genuinely self-hosted endpoint. Within its narrow scope, the result is a defensible answer to a question usually waved away: *what does each safeguard actually buy?* — here, exactly +32.5, +0.0, +75.0, +25.0 and +45.0 percentage points, give or take honest ranges, on the setups stated.

## Provenance and Reproducibility

Every statistic in this paper is lifted word for word from the repository's stored result files (`docs/figures/*-data.json` — the same files the committed figures render from, via `uv run chart.py`, with no API calls involved) or from the decision log (`docs/DECISIONS.md`, entries D12 through D24) for pilot results, hand-reads of transcripts, and the breakdown in the fifth experiment. A claim-by-claim mapping from each claim to its number to its source file is in the companion presenter pack (`forge-gap-presenter-pack.md`). The harness, the injectors, the grading program and the statistics are all covered by 12 offline test suites (77 tests) run automatically on every change.

## References

The four guardrail primitives (error-recovery/retry, corrective re-prompting, submit prodding, output validation) are reproduced as established practice in LLM-agent engineering; the project does not trace them to specific publications, and no citations are invented for them. The statistical methods are standard:

- Wilson, E. B. (1927). Probable inference, the law of succession, and statistical inference. *Journal of the American Statistical Association*, 22(158), 209–212. (The Wilson score interval.)
- Newcombe, R. G. (1998). Interval estimation for the difference between independent proportions: comparison of eleven methods. *Statistics in Medicine*, 17(8), 873–890. (Method 10, the "square-and-add" interval used for all between-arm gaps.)

Model and API documentation recorded in the repository README: the OpenRouter quickstart and tool-calling guides, and the GLM-4.6 model page (openrouter.ai).
