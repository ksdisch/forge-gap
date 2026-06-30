# forge-gap — Project Guide
*Point-in-time guide · updated 2026-06-29 (S7 complete) · branch `main` (HEAD `e00e338`) · stages **S0–S7 done & merged***

> **Update log (this refresh).** The first cut this morning (HEAD `ec71927`) covered S0–S5 and called S6 "in active development." Two stages have since landed and **resolved this guide's headline caveat:**
> - **S6 (PR #10):** the second guardrail (retry-nudge) + a malformed-call fault → a **measured null** — GLM self-corrects the bad call from the error hint, so the nudge changed nothing.
> - **S7 (PR #12):** the *natural-gap hunt* — hardened the task itself until GLM should break → **it didn't (8/8 twice); no natural gap.**
> The morning guide's #1 weakness ("the headline is an *injected* gap; the natural-gap stretch isn't done") is now **answered with evidence.** The project's real story sharpened to: **one positive result and two honest nulls, each gated by the same confidence-interval test.** Sections updated throughout; the old §0 "live / mid-surgery" note is now historical (folded into §0 below).

---

## 1. Snapshot (TL;DR)

- **What it is:** a small Python harness that **reproduces and measures** how much a reliability *guardrail* raises a self-hosted model's success rate on a multi-step tool-use task. Model: **GLM-4.6** via OpenRouter (OpenAI-compatible API). The deliverables are honest *figures*: a **gap-closure chart** (where a guardrail helps) and a **null chart** (where it doesn't), each with real confidence intervals.
- **Stack:** Python 3.11+, `uv` (venv + deps), `openai` SDK (→ OpenRouter), `python-dotenv`, `matplotlib`. No framework, no server — a measurement harness run with `uv run <script>`.
- **Maturity:** young but unusually disciplined — **~4 days old** (Jun 26→29 2026), ~20 commits, **12 merged PRs**, one human author (+ Claude co-author). **Stages S0–S7 are all done & merged**; S8–S12 are open/optional.
- **How to run:** `uv run verify.py` (smoke) → `uv run agent.py` (one run) → `uv run ablation.py z-ai/glm-4.6 40 0.6` (the headline 2-arm measurement) → `uv run malformed_ablation.py` (the S6 3-arm null) → `uv run pilot.py` / `pilot.py v2` (the S7 natural-gap hunt) → `uv run chart.py` (redraw both figures, no API). Offline tests: `uv run test_*.py` (10 suites).
- **The single most interesting thing:** the project treats **methodological honesty as the deliverable.** Across four probes it found **one** real effect (an injected-fault gap that error-recovery closes, +32.5%) and **kept reporting honest nulls** where there wasn't one (retry-nudge on malformed calls; the entire natural-gap hunt). Every claim — win *or* null — passes the same statistical gate that is *allowed to return "no result."* Most portfolios show only wins; this one shows the nulls and explains why they're informative.

---

## 0. What "done" means here — the honest shape of the results

forge-gap is now a **complete, self-consistent story**, not a work-in-progress. Three measured outcomes, all on GLM-4.6, all gated by the same Wilson/Newcombe interval + straddles-zero test:

| Stage | Testbed | Result | Reading |
|---|---|---|---|
| **S4** | injected **transient 503s** (N=40, rate 0.6) | baseline 67.5% → +error-recovery 100%; **+32.5%** (Newcombe [+17.3, +48.0], clears 0) | **a real effect** — the one positive bar |
| **S6** | injected **malformed calls** (N=20, rate 0.6) | all three arms 100%; gaps **+0.0%** (Newcombe [−16.1, +16.1], straddles 0) | **a null** — GLM self-corrects; no guardrail needed |
| **S7** | **no injection**, hardened task (v1 & v2) | GLM **8/8 both times** | **no natural gap** — a strong model doesn't break on its own here |

The throughline: **a guardrail only earns a bar where the model can't help itself.** S4's win was *turn-exhaustion* recovery (the bare loop retries on the model's own turn budget and runs out); malformed calls (S6) and a merely-harder task (S7) don't create that condition for GLM-4.6, so they measure null — and the project says so, on the figures and in the docs.

*(Historical note: an earlier cut of this guide flagged S6 as "mid-surgery on a shared working tree." That resolved cleanly — S6 merged via PR #10, S7 via PR #12; `main`'s working tree is clean.)*

---

## 2. Purpose & problem

**The problem.** People want to run cheaper / self-hosted models (here GLM-4.6) as agents — loops that call tools, read results, and act. Those models fail more often than frontier models on multi-step tool tasks. The industry answer is *reliability guardrails* (retry on error, nudge the model to fix a bad call, validate before submitting). The question nobody answers cleanly is: **how much does each guardrail actually buy you, with real error bars, on this model — and where does it buy you nothing?**

**What forge-gap does.** It builds the smallest end-to-end testbed where that question has a defensible numeric answer: a fixed task, a deterministic grader, a no-help baseline, one guardrail at a time, and proper proportion statistics on the *difference* between "with" and "without" — including the honesty to report "no difference."

**Who it's for / why it matters.** Primarily a **learning + interview-prep vehicle** for the author (built to be defended line-by-line), but the underlying question is real engineering: *quantifying* reliability mechanisms instead of asserting "retries help." The framing is deliberately modest and everywhere: *"reproduced and measured a known primitive — here's the narrow, measured delta,"* never *"I invented this."*

---

## 3. Capabilities — current state

### Working today (all merged & tested on `main`)
- **GLM client** (`glm.py:50` `chat()`) — thin OpenRouter wrapper, forwards `tools`/`tool_choice`/`temperature`/`max_tokens`, **fails loud** on a missing key (`glm.py:37`).
- **Scenario-agnostic agent loop** (`agent.py` `run()`) — the bare **reason→act→observe** cycle; recognizes the terminal `submit_answer`; ends in `submitted` / `no_submit` / `max_steps`. **Two opt-in guardrail toggles, off by default:** `recover` (error-recovery — the *harness* retries a *transient* fault, **no** model turn) and `nudge` (retry-nudge — one corrective re-prompt for a *malformed* call, **costs** a model turn).
- **Two tasks, as data** — `scenario.py` (the S2 chained 2-lookup, ground truth 158) and `scenario_hard.py` (the S7 hardened task: **v1** = 4-lookup chain through 15 confusable records, order named *by description* so the model must **disambiguate**; **v2** = 5-lookup + per-zone tax through ~25 records with a near-duplicate-customer distractor — "Globex" vs "Globex Labs").
- **Deterministic oracle** (`oracle.py` `grade()`) — exact numeric comparison to independently-computed ground truth; **never an LLM judge.**
- **Two fault injectors** (`faults.py`) — `with_faults` (seeded **transient 503**) and `with_malformed_faults` (the S6 **reject-and-hint**: an armed tool rejects the documented param with a `400 … use 'id' instead` hint; **permanent** so error-recovery ignores it, **sticky** so only a corrected call clears it). Both non-mutating (`rate=0` ≡ clean).
- **N-trial runner** (`runner.py` `run_arm`) — one arm, N trials → k/N + every trajectory.
- **Proportion statistics** (`stats.py`) — `wilson` (per-arm CI), `newcombe_diff` (CI on the gap), `excludes_zero` (the honesty gate).
- **N-arm ablation harness** (`ablation.py` `run_arms`; `run_ablation` repackages the 2-arm shape so the S4/S5 figure stays byte-compatible) — runs any list of arms over identical seeded faults; each arm gets a Wilson CI + a Newcombe gap vs the shared baseline. `malformed_ablation.py` is the S6 3-arm experiment; `pilot.py` is the S7 cheap, pilot-gated natural-gap hunt.
- **Two deliverable figures** (`chart.py` → `docs/figures/`): `gap-closure.png` (S4/S5 2-bar, `build_figure`) and `malformed-gap.png` (S6 3-bar null, `build_multi_figure`) — both from *saved, vendored* numbers, **no API**, with honesty captions.
- **Ten offline test suites** — oracle, faults, runner, stats, recover, ablation, chart, malformed, nudge, scenario_hard (network-free). I re-ran the seven that existed this morning: green; the S6/S7 suites are reported green in PRs #10/#12.
- **A learning spine** — `docs/ROADMAP.md` (incl. a Mermaid phase map), `DECISIONS.md` (D1–D20, an ADR log), `LEARNING.md`, + `check_docs.py` freshness gate.

### The three measured results
See the table in **§0**. The headline positive (S4): baseline **27/40 = 67.5%** (Wilson [52.0, 79.9]) → +error-recovery **40/40 = 100%** (Wilson [91.2, 100]), gap **+32.5%** (Newcombe [+17.3, +48.0]); the mechanism absorbed **104** transient 503s at the harness, spending zero model turns. The two nulls (S6, S7) are *findings*, not absences of work — see §5/§7.

### Open / optional (S8–S12, not started)
- **A third guardrail for the *validation gap*** — S7's key insight: a hard task's natural failures are *wrong-answer-with-no-error* (the model picks the wrong record and confidently submits). No tool error fires, so neither existing guardrail can see it; catching those needs a *validation* mechanism (check the answer before submit) — a genuinely different guardrail, and it would need a new "wrong-record" fault to measure against.
- **More models** (the harness is model-parameterized) — turns "no natural gap on GLM-4.6" into a cross-model statement; and **more distinct seeds** to tighten the S6 null (it ran N=20).
- **CI** (see §10).

---

## 4. Architecture & how it works

**Architectural style:** a tiny **layered measurement pipeline** built bottom-up, each layer a single-purpose pure-ish module, with **task-as-data** as the central seam.

```
   scenario.py  /  scenario_hard.py          faults.py (optional wrapper)
        ┌──────────────┐              ┌──────────────────────────────────┐
        │  Scenario     │  with_faults / with_malformed_faults            │
        │ (frozen data):│ ───────────► returns a NEW faulted Scenario      │
        │ tools+registry│              (original untouched)                │
        │ +ground_truth │              └──────────────────────────────────┘
        └──────┬────────┘
               │  passed in
               ▼
  agent.py  run(scenario, recover=…, nudge=…)  ── reason→act→observe loop
    reason → chat() asks GLM                    ── glm.py (OpenRouter)
    act    → dispatch[_with_recovery]           ── the recover/nudge toggles wrap the LOOP
    observe→ feed result back, repeat
               │ writes trajectory.jsonl
               ▼
  oracle.py  grade(submitted, ground_truth)     ── deterministic PASS/FAIL
               │
               ▼
  runner.py  run_arm(label, model, N)           ── one arm, N trials → k/N
               │
               ▼
  ablation.py  run_arms(arms, …)                ── N arms, SAME seeds (paired)
    │  stats.py: wilson() per arm · newcombe_diff() per gap · excludes_zero() gate
    ▼  writes runs/*-summary.json → vendored to docs/figures/*-data.json
  chart.py  build_figure / build_multi_figure   ── the deliverable PNGs (no API)
```

**The one mental model:** *the task is data; the mechanism wraps the loop.* A `Scenario` is a frozen dataclass (`scenario.py:31`) — tools, registry, ground truth — passed *into* `agent.run`. Guardrails are **toggles on the loop** (`recover`, `nudge`), never edits to the task. That separation is what lets the ablation push a **byte-identical** scenario through several arms and attribute any difference purely to the mechanism. Faults are injected by returning a *new* `Scenario` (`dataclasses.replace`), so the clean baseline is never mutated. S6 generalized the harness from two arms to **N** (`run_arms`) and the chart to **N bars** — adding an arm is a list entry, not a rewrite.

**Three non-obvious mechanisms worth understanding:**
1. **Where the retry lives is the whole point.** The bare loop *already* retries a failed tool — but the *model* does it, re-calling on its next turn and burning one of its ~6 reasoning steps each time. Under heavy faults that exhausts the budget (`max_steps`). **Error-recovery doesn't add retrying; it moves it** to the harness (`agent.py` `dispatch_with_recovery`), where a retry costs *no* model turn. "Do the same thing somewhere cheaper."
2. **Stringly-typed retryability** (`agent.py` `_is_retryable`) — the loop decides whether to retry by matching substrings (`"503"`, `"timeout"`, …) in the *error string*, not by exception type. This decouples the core loop from any fault module *and* is what makes the S6 malformed fault (`400 invalid_argument`) **permanent for free**: its string matches no hint, so error-recovery structurally ignores it. That's **guardrail specificity** built into the type system of strings, not bolted on.
3. **Guardrail ↔ fault matching is a designed, tested property.** error-recovery↔transient, retry-nudge↔malformed. S6's 3-arm experiment *proves* the mismatch is null (error-recovery does nothing to a malformed call) — the "wrong" guardrail is kept in the experiment precisely to **show** it does nothing, which is what makes the matched result legible.

---

## 5. Build history & key decisions

A clean stage ladder — each "S" ≈ one session and one PR; the *why* behind every choice is in `docs/DECISIONS.md` (D1–D20, effectively ADRs). The load-bearing calls:

- **S0 — foundation (`19647de`, `edcd093`).** Minimal client + a tool-calling smoke test. **Decision: prove tool-calling on day one** — every later stage depends on it.

- **S2 — task + oracle (PR #1).**
  - **D2 — deterministic oracle, never an LLM judge** ⭐. An LLM judge is "self-graded homework"; to measure a *small* delta you need a fixed ruler.
  - **D3 — make failures MECHANICAL, not COGNITIVE** ⭐. A *chained* lookup with *trivial* math, so failures are wrong-tool/field/step (recoverable), not can't-do-math.
  - **D4 — capture the answer via a `submit_answer` terminal tool** — a missing submit is a clean, classifiable failure; the oracle grades a real number.

- **S3 — does a gap even exist? (PR #4).** The project's intellectual hinge.
  - **D12 — the kill-trigger fired** ⭐. GLM scored **20/20** clean → no natural gap. The pre-registered "stop and pivot" was *honored*. Decision: **inject deterministic faults as a foundation and disclose it**, keeping a natural-gap hunt as a stretch. Inject *first* because you can only unit-test a recovery mechanism if you can **reproduce the failure on demand**.
  - **D13 — "N" = number of *distinct* seeds** ⭐. Two N=20 runs failed the *identical* seeds → completion is dominated by the fault *pattern*; re-running a seed is reproducibility, not more data.

- **S4 — first guardrail + statistics (PR #7).** The headline measurement.
  - **D14 — error-recovery before retry-nudge** ⭐. S3's gap was 100% retry-exhaustion, which a no-turn-cost retry directly rescues. (Reversed the cross-project plan's order; flagged as a sign-off, not silently overridden.)
  - **D16 — Wilson per arm, Newcombe on the difference, straddles-zero is the gate.** A completion rate is a *proportion*; near 0/100% with small N the textbook Wald (±std) interval misbehaves and can escape [0,1]. Newcombe builds the interval *for the difference itself* — the number actually reported.
  - **D17 — a real result by the gate** ⭐. +32.5%, Newcombe [+17.3, +48.0], clears 0. 100% is a boundary, so the honest read of the mechanism arm is its Wilson floor (91.2%).

- **S5 — the chart (PR #8).**
  - **D18 — draw the chart now.** Data already measured + saved; the figure is the literal deliverable. **Vendoring** the result into a tracked `…-data.json` (so it regenerates after a clean clone) + a `test_chart.py` assertion **pinning the vendored data to the measured numbers** so the figure can't drift.

- **S6 — second guardrail + malformed fault → a measured NULL (D19, PR #10).** Built **retry-nudge** (`nudge` toggle — one corrective re-prompt, costs a model turn) + `with_malformed_faults` (reject-and-hint; permanent + sticky). A 3-arm ablation (baseline / +error-recovery / +retry-nudge) on the malformed testbed (**N=20, rate 0.6**) measured **all three arms 100%**, both gaps **+0.0%** (Newcombe [−16.1, +16.1], straddles 0) → **null**. *Why:* GLM-4.6 reads the `400` hint *as a tool result* and self-corrects next turn, so neither guardrail has work — the nudge fired **26** re-prompts that changed nothing. The null **sharpens S4**: a guardrail helps only where the model can't help itself. The honest-null risk was *pre-flagged before spending* and a cheap pilot run first. Also generalized the harness to **N arms** + the chart to **N bars**.

- **S7 — the natural-gap hunt → NO GAP (D20, PR #12).** The headline stretch from D12: drop injection and *harden the task itself* until GLM fails on its own, then re-run guardrails. Built `scenario_hard.py` (v1: 4-lookup chain / 15 confusable records / disambiguate-by-description; v2 escalation: 5-lookup + per-zone tax / ~25 records / "Globex" vs "Globex Labs" distractor) + a pilot-gated runner (`pilot.py`). Pilot v1 → **8/8**; per a pre-agreed **bounded escalation** (push difficulty once, a ≥7/8 result stops), pilot v2 → **8/8**; declared done. Across four probes (20/20 clean, self-heals malformed, 8/8 v1, 8/8 v2) **GLM-4.6 shows no measurable natural gap** at reasonable mechanical difficulty — so injected faults are the honest way to study guardrails here, exactly as disclosed. *Load-bearing insight:* a hard task's natural failures are **wrong-answer-with-no-error** (a *validation* gap), which neither existing guardrail can see — a found gap would have demanded a *new* guardrail, not rescued the two we have.

---

## 6. Concepts & vocabulary

| Term (industry name) | One-line meaning | Where it lives here |
|---|---|---|
| **reason→act→observe loop** (agent loop) | decide → run a tool → feed the result back → repeat | `agent.py` `run()` |
| **tool-calling** (function calling) | model emits a structured call to a named function instead of prose | `scenario*.py` schemas |
| **deterministic oracle / ground truth** | code that knows the right answer and returns PASS/FAIL — never an LLM | `oracle.py` |
| **mechanical vs cognitive failure** | machinery broke (recoverable) vs model genuinely can't reason (not targeted) | `scenario*.py` |
| **fault injection** | deliberately, reproducibly making a tool fail (seeded 503 / malformed call) | `faults.py` |
| **transient vs malformed fault** | service hiccups (any retry clears it) vs the call itself is wrong (only a *corrected* call clears it) | `ToolUnavailable` / `MalformedCall` |
| **error-recovery vs retry-nudge** | harness retries, **no** model turn (transient) vs re-prompt the model, **costs** a turn (malformed) | `agent.py` `recover` / `nudge` |
| **guardrail specificity** | each guardrail fixes its own fault type; a mismatch measures null (proved in S6) | S6 / D19 |
| **arm / arm-as-config / ablation** | one config under test as data (`{label, run_kwargs}`); toggle one factor, hold the rest | `ablation.py` `run_arms` |
| **Wilson / Newcombe interval** | honest CI for one proportion / for the *difference* of two proportions | `stats.py` |
| **straddles-zero gate / measured null** | if the difference interval includes 0 → report "no effect," not a win | `stats.py` `excludes_zero` |
| **paired comparison** | all arms face the *same* per-trial fault pattern (same seed i) | `ablation.py` |
| **validation gap** | a wrong-answer-with-no-error failure (wrong record picked + submitted) — no error fires, so retry/nudge can't see it | S7 / D20 |
| **bounded escalation / pilot-gating** | de-risk with a tiny cheap run first; if it aces, raise difficulty a *fixed* number of times, then stop | `pilot.py` / D20 |
| **vendoring** | commit a copy of a gitignored file so the build doesn't depend on scratch | `docs/figures/*-data.json` |

---

## 7. Recruiter & hiring-manager lens

A reviewer *will* clone this and poke it. The honest two-sided read.

### Reads as a strength
- **Methodological honesty as an artifact, not a footnote.** The pre-registered kill-trigger that *fired and was honored*; the `excludes_zero` gate that *can* return "not a result"; the word **INJECTED** on the figure. Senior-level judgment, and the single most impressive thing here.
- **Reports honest nulls — rare, and a strong research-maturity signal.** *Two of the three* measured results are nulls (retry-nudge on malformed calls; the whole natural-gap hunt), each pushed through the same CI gate and explained (guardrail specificity; the model self-heals; no natural gap exists). Most candidates show only wins; showing nulls *and why they're informative* is unusual and credible.
- **Followed the hard question to its end (S7).** The natural-gap hunt deliberately tried to *break the project's own headline* — hardened the task until GLM should fail — and reported the negative result with a bounded, pre-agreed stopping rule. The opposite of cherry-picking.
- **Genuine statistical literacy.** Wilson + Newcombe (not ±std), a correct account of *why* Wald breaks at the boundaries, "N = distinct seeds," reporting a 100% bar as its Wilson floor.
- **Clean separation of concerns + disciplined restraint.** One job per module; the `Scenario` seam; mechanism-wraps-the-loop; deferring abstractions until the second use-case exists (D11) and then generalizing cleanly to N arms (S6).
- **Tests + secret/cost hygiene.** Ten offline suites; a fake-model injection so the loop + CI math are tested with **zero API spend**; CI math pinned to hand-computed values; chart tests pin vendored data to measured numbers. `.env` gitignored with a committed `.env.example`; the client fails loud and never prints the key; the `max_tokens` cap documented as *cost hygiene, explicitly not a reliability mechanism*.

### Reads as a weakness / risk — and how to talk about it
- **All results are on one model (GLM-4.6) — the real residual now.** S7 *directly tested* whether a natural gap exists and found none (8/8 twice), so the injected framing is a **demonstrated necessity**, not an unexamined shortcut — the old "isn't that circular?" critique is largely answered. The honest caveat that remains: *"no natural gap" and "+32.5%" are statements about this model at this difficulty.* **Framing:** the harness is model-parameterized; a second model is the highest-value next move and turns this into a cross-model claim.
- **Small-N nulls are "no *detectable* effect," not "provably zero."** The S6 null ran **N=20** (Newcombe ±16 pts), so a true effect smaller than ~16 pts could hide. **Framing:** be the one to say it — "it's a null at N=20; I'd raise N to tighten the bound; I reported the interval precisely so no one over-reads it." That precision is itself the strength.
- **No CI/CD.** The ten suites run manually (`uv run test_*.py`); no GitHub Actions on push, and `check_docs.py` is explicitly "a smoke alarm, not a commit gate." For a project that prides itself on rigor this is the most visible fixable gap. **Do it before interviews (§10).**
- **Hand-rolled test harness, not pytest.** A custom `check()`/`_failures` pattern — zero deps, but non-standard; a reviewer will notice. Defensible ("no test deps for a teaching repo"), but say you'd move to pytest for anything shared.
- **Stringly-typed retryability** (`_is_retryable` substring-matches the error). Documented as deliberate (HTTP status signaling is already stringly-typed; it decouples the loop and makes malformed permanent for free), but fragile — a tool whose *legitimate* output contained "retry" could be misclassified. A known, named trade-off.
- **Young, solo, short history.** ~4 days, one author. High depth-per-day and exceptional docs, but small and early — a learning vehicle, not a production system, and not pitched as one.

**Bottom line for a hiring manager:** a *small* repo that demonstrates *large* judgment — experimental design, statistical honesty, restraint, and the rare willingness to report and explain nulls. Its weaknesses are "young project" (no CI, one model, small-N nulls), not "bad engineering." The two highest-signal fixes before showing it: **add CI**, and **run a second model.**

---

## 8. Interview readiness

**Questions a sharp interviewer would ask:**
1. Walk me through the architecture — how does one loop run different tasks *and* different guardrails?
2. Why Wilson + Newcombe instead of mean ± std or a t-test? Why does the textbook interval break here?
3. Your one positive result is on an *injected* gap — isn't that circular? How do you know GLM has no natural gap?
4. Two of your three results are nulls. Why is a null a result, and how do you defend the N=20 one?
5. Why is "N = distinct seeds," not "number of runs"? Why does that matter for power?
6. Why a deterministic oracle instead of an LLM judge — and when *would* an LLM judge be acceptable?
7. error-recovery vs retry-nudge — the difference, and why error-recovery first?
8. What breaks at 100× / more arms / a model you can't injection-control? What would you do differently?

---
**Answer scaffolds (speak from these — all grounded in the repo):**

1. **Architecture.** Task is data (`Scenario`, a frozen dataclass) passed *into* a scenario-agnostic loop; guardrails are toggles *on the loop* (`recover`, `nudge`), never edits to the task. Faults wrap the scenario by returning a *new* one. So the ablation pushes a byte-identical task through N arms and the only difference is the mechanism → the gap is attributable.
2. **Stats.** A completion rate is a *proportion*. Near 0/100% with small N, the Wald (±std) interval can run outside [0,1] and understates uncertainty. Wilson behaves at the edges; Newcombe ("square-and-add," method 10) builds the interval *for the difference itself*, the number I report. Straddles 0 → "no clear effect" (`excludes_zero`).
3. **Circularity — now answered.** Concede the positive bar is on a controlled, *injected* testbed (labeled INJECTED on the figure). But S7 *went looking* for a natural gap — hardened the task two levels until I'd expect mechanical failure — and GLM aced it 8/8 both times. So "use injected faults" isn't a shortcut; it's a *demonstrated necessity* on this model. The honest residual is that it's one model at one difficulty band.
4. **Nulls.** A null *is* a result when it's gated: the S6 difference interval straddles 0, so I report "no effect," not silence. It's informative — it shows **guardrail specificity** (error-recovery can't touch a permanent malformed call) and that GLM self-corrects from an error hint. Defending N=20: it's "no *detectable* effect at ±16 pts," not "provably zero" — I'd raise N to tighten it, and I report the interval so no one over-reads the bar.
5. **Seeds.** Deterministic per-trial seeds make completion depend on the fault *pattern*, not GLM's randomness — two N=20 runs failed identical seeds. So re-running a seed is reproducibility; power comes from *more distinct* seeds (and a higher fault rate for a bigger gap).
6. **Oracle.** Measuring a small delta needs a fixed ruler; an LLM judge imports its own blind spots + sycophancy. It's acceptable only for open-ended outputs (prose quality) where there's no ground truth — and even then you'd calibrate against humans. Here the answer is a number; exact comparison is honest.
7. **Two retries.** error-recovery = *harness* retries a transient failure in one step, **no** model turn. retry-nudge = re-prompt the *model* to fix its call, **costs** a turn. error-recovery first because S3's gap was 100% retry-exhaustion, which a no-turn retry directly fixes; retry-nudge needed a *malformed* fault to even have a chance (S6) — and there it measured null.
8. **Scale / what I'd change.** Adding arms is a list entry (arm-as-config). The real limits: small-N nulls need more seeds; results are one model; and the approach assumes you can *inject* faults. Top two next moves: **CI**, then a **second model** — that turns "no natural gap on GLM-4.6" into a cross-model statement. The S7 insight also points at a *third* guardrail (validation, for wrong-answer-no-error failures) the current two can't cover.

---

## 9. Talking points

**Elevator (~45–60s, spoken):**
"forge-gap answers one question honestly: when you bolt a reliability guardrail onto a cheaper model running as an agent, *how much* does it actually help — with real error bars? I run a fixed multi-step tool task, grade it with a deterministic checker instead of another AI, and compare a no-help baseline against one guardrail at a time using proper proportion statistics. The honest part is that most of my results are *nulls*, reported as nulls: one guardrail closed a real gap — plus thirty-two percent, interval clears zero — but the second one did nothing, because the model just fixes its own mistake; and when I hardened the task to make the model fail on its own, it didn't. So the headline isn't 'guardrails are great' — it's 'here's exactly where one helps, measured, and here's where it provably doesn't.'"

**Deep cut (~2 min, spoken):**
"The decision I'm proudest of is what happened when my plan kept *not* working. I'd pre-registered a kill-trigger — if the model already passes about eighty-five percent, stop, there's nothing to measure. It passed twenty out of twenty. So instead of faking a gap I built a deterministic fault injector and said so on the figure. Then the statistics: a completion rate is a proportion, so mean-plus-or-minus-standard-deviation is the wrong tool — near a hundred percent it hands you an interval above a hundred percent, which is nonsense. I used Wilson intervals per arm and a Newcombe interval on the *difference*, with a rule that if that interval includes zero I'm not allowed to call it a win. That rule earned its keep twice: my second guardrail measured a clean null, and then — the part I'd lead with — I went hunting for the model's *natural* failures, hardened the task two levels until it should have broken, and it scored eight out of eight both times. A lot of people would have buried that. I shipped it as the result: on this model, you *need* injected faults to study guardrails honestly — and I can prove it."

---

## 10. Gaps, debt & next moves

| Priority | Item | Effort | Note |
|---|---|---|---|
| **High** | Add a GitHub Actions workflow running the 10 offline suites on push | ~30 min | The cheapest credibility win — turns "I have tests" into "tests gate the repo." The most visible remaining gap. |
| **High** | Run a **second model** through the harness (it's model-parameterized) | ~1 session | Turns "no natural gap on GLM-4.6" / "+32.5%" into cross-model statements. Highest-signal scientific extension. |
| **Medium** | Tighten the **S6 null** from N=20 → N=40 distinct seeds | ~20 min + API | Shrinks the ±16-pt Newcombe bound so the null is "no effect to a tighter tolerance." |
| **Medium** | A **third guardrail for the validation gap** (+ a wrong-record fault to measure it) | multi-session | S7 showed natural failures would be *wrong-answer-no-error* — a class the current two guardrails can't see. The honest next frontier. |
| **Low** | pytest migration; tidy gitignored `runs/` scratch | minor | Convention / cosmetics. |

**Owning the debt is itself a signal** — the two moves that would most change how this reads to a reviewer are **CI** and a **second model**; everything else is refinement on an already-complete, honest story.

---

## 11. Map of the codebase

| File | What it is |
|---|---|
| `glm.py` | Minimal GLM-via-OpenRouter client (`chat()`, `MODEL`); fails loud on a missing key. |
| `agent.py` | The reason→act→observe loop + grading; the `recover` (error-recovery) **and** `nudge` (retry-nudge) toggles + the retryability predicate. |
| `scenario.py` | The S2 task as a frozen `Scenario` — chained 2-lookup + `submit_answer` + ground truth (158). |
| `scenario_hard.py` | **S7** hardened task: v1 (4-lookup / 15 confusable records / disambiguate-by-description) + v2 (5-lookup + tax / ~25 records / near-dup distractor). |
| `oracle.py` | Deterministic grader (`grade()`) — exact numeric comparison, never an LLM. |
| `faults.py` | Two injectors: `with_faults` (transient 503, S3) + `with_malformed_faults` (reject-and-hint, S6; permanent + sticky). |
| `runner.py` | N-trial single-arm runner (`run_arm`) → raw k/N + every trajectory. |
| `stats.py` | `wilson` (per-arm CI), `newcombe_diff` (gap CI), `excludes_zero` (the honesty gate). |
| `ablation.py` | N-arm harness (`run_arms`; `run_ablation` = the 2-arm S4 shape) over identical seeds; Wilson + Newcombe per arm. |
| `malformed_ablation.py` | **S6** 3-arm experiment (baseline / +error-recovery / +retry-nudge) on the malformed testbed → the measured null. |
| `pilot.py` | **S7** cheap, pilot-gated natural-gap hunt on the hardened task (no guardrail arms — surfaces & classifies misses). |
| `chart.py` | Renders both deliverable PNGs from *saved* numbers — `build_figure` (2-bar) + `build_multi_figure` (N-bar). No API. |
| `verify.py` | Smoke test: plain chat + one tool-calling round-trip. |
| `check_docs.py` | Learning-spine freshness check (done stages must be written up). |
| `test_*.py` | **Ten** offline suites (oracle, faults, runner, stats, recover, ablation, chart, malformed, nudge, scenario_hard); network-free. |
| `docs/ROADMAP.md` · `DECISIONS.md` · `LEARNING.md` | The learning spine: where we are (incl. a Mermaid phase map) · why (D1–D20) · what it means + glossary. |
| `docs/figures/gap-closure.png` · `malformed-gap.png` (+ `*-data.json`) | The two deliverable figures + their vendored (tracked) source numbers. |
| `pyproject.toml` | `uv` app (not a package); deps: `openai`, `python-dotenv`, `matplotlib`. |

---
*Generated by `/project-guide` (S7-completion refresh). Evidence: full source read incl. the S6/S7 additions (`malformed_ablation.py`, `scenario_hard.py`, `pilot.py`, the N-arm/N-bar generalization, the `malformed-gap` figure), the `docs/` spine D1–D20, git log + 12 merged PRs, S7 confirmed merged (PR #12, HEAD `e00e338`), and the vendored result JSONs. Where a result is a null, the guide says so and reports the interval rather than rounding it to a win.*
