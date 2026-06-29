# forge-gap — Project Guide
*Point-in-time guide · 2026-06-29 · branch `main` (HEAD `ec71927`, S5 merged) · S6 in active development*

---

## 1. Snapshot (TL;DR)

- **What it is:** a small Python harness that **reproduces and measures** how much a reliability *guardrail* raises a self-hosted model's success rate on a multi-step tool-use task. The model is **GLM-4.6** (reached via OpenRouter's OpenAI-compatible API). The deliverable is one honest figure: a **gap-closure chart** with real confidence intervals.
- **Stack:** Python 3.11+, `uv` (venv + deps), `openai` SDK (pointed at OpenRouter), `python-dotenv`, `matplotlib`. No framework, no web server — it's a measurement harness, run with `uv run <script>`.
- **Maturity:** young but unusually disciplined — **4 days old** (Jun 26→29 2026), ~14 commits, 8 merged PRs, one human author (+ Claude co-author). Stages **S0→S5 are done and merged**; **S6 is mid-build** (uncommitted, see §0 below).
- **How to run:** `uv run verify.py` (smoke test) → `uv run agent.py` (one task run) → `uv run ablation.py z-ai/glm-4.6 40 0.6` (the two-arm measurement) → `uv run chart.py` (redraw the figure, no API). Offline tests: `uv run test_*.py`.
- **The single most interesting thing:** the project treats **methodological honesty as a first-class deliverable**. The headline gap is *manufactured* (faults are injected), and the project says so *on the figure itself* (the word **INJECTED** in the caption), enforces a pre-registered "kill-trigger" that actually fired, and gates every claim behind a statistical test that can return "no result." That discipline — not the code — is the portfolio asset.

---

## 0. Live state note (read this first — it's moving)

This repo shares a working directory with a **concurrent build session** (a known constraint — see the project's auto-memory). During the writing of this guide, **S6's implementation landed in real time**: `faults.py` grew from 69→134 lines and the S6 test suite flipped from red to green between two of my reads. So the snapshot below is precise as of **2026-06-29 ~01:00**, but S6 specifics will move.

**Committed/merged (stable, on `main`):** S0–S5.
**Uncommitted working-tree changes right now:** `faults.py` (+`with_malformed_faults`, `MalformedCall`), `docs/DECISIONS.md` (+D19 brief), and untracked `test_malformed.py`. A local `feat/s6-retry-nudge` branch exists. **Caveat for showing the repo:** these S6 changes currently sit on `main`'s working tree rather than on the feature branch — `git status` on a fresh clone-and-pull would look clean, but *this* checkout looks mid-surgery. Land them on `feat/s6-retry-nudge` before a demo (see §10).

---

## 2. Purpose & problem

**The problem.** People want to run cheaper or self-hosted models (here GLM-4.6) as agents — loops that call tools, read results, and act. Those models fail more often than frontier models on multi-step tool tasks. The industry answer is *reliability guardrails* (retry on error, nudge the model to fix a bad call, validate before submitting). The honest question nobody answers cleanly is: **how much does each guardrail actually buy you, with real error bars, on this model?**

**What forge-gap does about it.** It builds the smallest possible end-to-end testbed where that question has a defensible numeric answer: a fixed task, a deterministic grader, a no-help baseline, one guardrail at a time, and proper proportion statistics on the *difference* between "with" and "without."

**Who it's for / why it's worth solving.** Primarily a **learning + interview-prep vehicle** for the author (the repo is explicitly built to be defended line-by-line), but the underlying question is real engineering: *quantifying* reliability mechanisms instead of hand-waving "retries help." The framing is deliberately modest and repeated everywhere: *"reproduced and measured a known primitive — here's the narrow, measured delta,"* never *"I invented this."*

---

## 3. Capabilities — current state

### Working today (merged, tested, on `main`)
- **A reusable GLM client** (`glm.py:50` `chat()`) — a thin wrapper over OpenRouter's OpenAI-compatible endpoint that forwards `tools`/`tool_choice`/`temperature`/`max_tokens` through, and **fails loudly** if the key is missing (`glm.py:37`).
- **A scenario-agnostic agent loop** (`agent.py:128` `run()`) — the bare **reason→act→observe** cycle that drives any `Scenario`, recognizes a terminal `submit_answer` tool, and ends in exactly one of three classifiable states: `submitted` / `no_submit` / `max_steps`.
- **The task, as data** (`scenario.py`) — a frozen `Scenario` bundling a **chained two-step lookup** (`get_order` → `get_ship_rate`) plus trivial arithmetic, with ground truth (158) computed independently in Python.
- **A deterministic oracle** (`oracle.py:42` `grade()`) — exact numeric comparison to ground truth; lenient on format (`"$158"` passes), rejects non-numbers. **Never an LLM judge.**
- **A fault injector** (`faults.py:48` `with_faults`) — wraps the lookup tools to raise a **seeded transient 503** at a set rate; non-mutating (`rate=0` ≡ clean task).
- **An N-trial runner** (`runner.py:42` `run_arm`) — loops one arm N times, writes every trajectory, reports raw k/N.
- **Proportion statistics** (`stats.py`) — `wilson()` (per-arm CI), `newcombe_diff()` (CI on the gap), `excludes_zero()` (the honesty gate).
- **A two-arm ablation harness** (`ablation.py:48` `run_ablation`) — runs *baseline* vs *+error-recovery* over identical seeded faults, prints both Wilson CIs + the Newcombe gap + a verdict, writes `ablation-summary.json`.
- **The deliverable figure** (`chart.py` → `docs/figures/gap-closure.png`) — drawn from *saved* numbers, **no API call**, with the load-bearing honesty caption.
- **Seven offline test suites** — `test_oracle/faults/runner/stats/recover/ablation/chart`. I ran all seven during this review: **all pass**.
- **A learning spine** (`docs/ROADMAP.md`, `DECISIONS.md`, `LEARNING.md`) + a freshness checker (`check_docs.py`).

### The measured result (the point of the whole thing)
On the injected-fault testbed (GLM-4.6, **N=40** paired seeds, fault-rate **0.6**, temp **0.7**):

| Arm | Completion | Wilson 95% CI |
|---|---|---|
| Baseline (no mechanism) | **27/40 = 67.5%** | [52.0%, 79.9%] |
| + Error-recovery (harness retry) | **40/40 = 100%** | [91.2%, 100%] |

**Gap closed: +32.5%**, Newcombe 95% CI **[+17.3%, +48.0%]** → clears 0, and the Wilson bars don't overlap → a *real result* by the project's own gate. The mechanism arm absorbed **104** transient 503s at the harness, spending zero model turns. Baseline's 13 misses were **all** `max_steps` (retry-exhaustion).

### In progress (S6 — uncommitted as of this writing)
- ✅ **A second fault type** (`faults.py:95` `with_malformed_faults`) — a **malformed-call / reject-and-hint** fault: an "armed" tool rejects the documented parameter (`order_id`/`zone`) with a `400` hint and only accepts a *corrected* call (`id`/`region`). Built to be **permanent** (error-recovery must ignore it) and **sticky** (a blind resend keeps failing). Offline-proven by `test_malformed.py` (green).
- ⬜ **The retry-nudge mechanism** — a `nudge` toggle on `agent.run` (re-prompt the model to fix its call). **Not built yet** — `agent.run` still only has `recover`.
- ⬜ **The 3-arm experiment** (baseline / +error-recovery / +retry-nudge on the malformed testbed) — `ablation.py` still has only the two S4 arms; no malformed run dirs exist yet.

### Planned (not started)
- The **natural-gap stretch** (D12) — drop injected faults, harden the task until GLM fails on its *own* merits, re-run the same guardrails. This is the headline prize and remains future work.
- Extending the chart across more arms (S6–S12).

---

## 4. Architecture & how it works

**Architectural style:** a tiny **layered measurement pipeline** built bottom-up, each layer a single-purpose pure-ish module, with **task-as-data** as the central seam.

```
            scenario.py                 faults.py (optional wrapper)
          ┌──────────────┐            ┌────────────────────────────┐
          │  Scenario     │  with_faults / with_malformed_faults    │
          │ (frozen data):│ ─────────► returns a NEW faulted        │
          │ tools+registry│            Scenario (original untouched) │
          │ +ground_truth │            └────────────────────────────┘
          └──────┬────────┘
                 │  passed in
                 ▼
   agent.py  run(scenario, recover=…)  ── the reason→act→observe loop
     reason → chat() asks GLM           ── glm.py (OpenRouter)
     act    → dispatch[_with_recovery]  ── the recover toggle lives HERE (wraps the loop)
     observe→ feed result back, repeat
                 │ writes trajectory.jsonl
                 ▼
   oracle.py  grade(submitted, ground_truth)  ── deterministic PASS/FAIL
                 │
                 ▼
   runner.py  run_arm(label, model, N)        ── one arm, N trials → k/N
                 │
                 ▼
   ablation.py  run_ablation(...)             ── two arms, SAME seeds (paired)
     │  stats.py: wilson() per arm, newcombe_diff() on the gap, excludes_zero() gate
     ▼  writes runs/ablation-summary.json
   (vendored to) docs/figures/gap-closure-data.json
                 ▼
   chart.py  build_figure(...)                ── the deliverable PNG (no API)
```

**The one mental model to hold:** *the task is data; the mechanism wraps the loop.* A `Scenario` is a frozen dataclass (`scenario.py:31`) — tools, registry, ground truth — passed *into* `agent.run`. Guardrails are **toggles on the loop** (`recover=True`), never edits to the task. That separation is what lets the ablation push the **byte-identical** scenario through two different arms and attribute the difference purely to the mechanism. Faults are injected by returning a *new* `Scenario` (`dataclasses.replace`), so the clean baseline is never mutated.

**Two non-obvious mechanisms worth understanding:**
1. **Where the retry lives is the whole point.** The bare loop *already* retries a failed tool — but the *model* does it, re-calling the tool on its next turn, burning one of its 6 reasoning steps each time. Under heavy faults that exhausts the budget (`max_steps`). **Error-recovery doesn't add retrying; it moves it** to the harness (`agent.py:101` `dispatch_with_recovery`), where a retry costs *no* model turn. "Do the same thing somewhere cheaper."
2. **Stringly-typed retryability** (`agent.py:89` `_is_retryable`) — the loop decides whether to retry by matching substrings (`"503"`, `"timeout"`, …) in the *error string* `dispatch` returns, not by exception type. This deliberately **decouples the core loop from any specific fault module**: the same predicate catches a real OpenRouter 503 and the injected `ToolUnavailable`. It's also exactly what makes the S6 malformed fault (`400 invalid_argument`) *permanent* for free — its string matches no hint, so error-recovery leaves it alone, which is the structural separation between the two guardrails.

---

## 5. Build history & key decisions

The git history is a clean stage ladder — each "S" is roughly one session and one PR. The *why* behind every choice is captured in `docs/DECISIONS.md` (D1–D19), which is effectively an ADR log. The load-bearing calls:

- **S0 — foundation (`19647de`, `edcd093`).** A minimal client + a tool-calling smoke test. **Decision: prove tool-calling on day one** — every later stage depends on it, so make the risky thing fail early if it's going to.

- **S2 — task + oracle (PR #1).**
  - **D2 — deterministic oracle, never an LLM judge** ⭐. *Why:* an LLM judge is "self-graded homework" — the same class of system that can fail the task scores it, importing its blind spots + sycophancy as bias. To measure a *small* delta you need a fixed ruler. *Rejected:* LLM judge (rubber ruler).
  - **D3 — make failures MECHANICAL, not COGNITIVE** ⭐. The task is a *chained* lookup with *trivial* math. *Why:* the thesis is that GLM's failures are mechanical (wrong tool/field/step) and therefore **recoverable** by a guardrail. *Rejected:* hard-arithmetic tasks (manufacture cognitive failures — the wrong kind); two independent lookups (too easy, no gap).
  - **D4 — capture the answer via a `submit_answer` terminal tool** rather than scraping prose. A missing submit becomes a clean, classifiable failure; the oracle grades a real number.

- **S3 — does a gap even exist? (PR #4).** This is the project's intellectual high point.
  - **D12 — the kill-trigger fired** ⭐. GLM scored **20/20** on the clean task. A 100% baseline has nothing for a guardrail to recover, so there's **no natural gap**. The pre-registered "kill-trigger 1" said *stop and pivot* — and it was honored, not rationalized away. *Decision:* **inject deterministic faults as a foundation** (a controlled fault-recovery testbed) **and disclose it**, keeping a tuned natural gap as a *stretch*. *The reason inject-*first*:* you can only build and unit-test a recovery mechanism if you can **reproduce the failure on demand**; GLM's natural failures are stochastic and can't be a deterministic fixture. *Rejected:* fake/assume a gap; tune-first (burns effort chasing an uncertain gap before the mechanism exists); document-the-null-and-stop.
  - **D11 — the S3 runner is a lean diagnostic, not the S4 harness.** Resisted building CIs + arm-config up front. *Why:* premature abstraction — the seam for "arms-as-config" only appears when a second arm-*type* actually exists (S4).
  - **D13 — "N" = number of *distinct* seeds** ⭐. Two independent N=20 runs failed the *identical* seeds {4,9,16,18} — so completion is dominated by the fault *pattern*, not GLM's randomness. Re-running a seed is **reproducibility, not more data**. More statistical power = more distinct seeds.

- **S4 — first guardrail + statistics (PR #7).** The measurement.
  - **D14 — error-recovery before retry-nudge** ⭐. *Why:* S3's gap is 100% retry-exhaustion, which a *no-turn-cost* retry directly rescues; retry-nudge against a transient fault would measure ~null (the bare loop already self-retries). Highest-information first arm. *Honest process note:* this **reversed** the cross-project plan's ordering, so it was flagged as a sign-off question, not silently overridden; it proceeded because the change is additive/reversible.
  - **D16 — Wilson per arm, Newcombe on the difference, straddles-zero is the gate.** *Why:* a completion rate is a *proportion*; near 0%/100% with small N the textbook Wald (±std) interval misbehaves and can escape [0,1]. Wilson stays sane at the edges; Newcombe carries that into the *difference* (the number actually reported). *Rejected:* Wald difference; eyeballing whether two Wilson bars overlap (non-overlap is sufficient but not necessary for a real difference — it can hide a null or a real effect).
  - **D17 — the result is real by the gate** ⭐. +32.5%, Newcombe [+17.3, +48.0], clears 0. 100% is a boundary, so the *honest* read of the mechanism arm is its Wilson floor (91.2%), not "certainly perfect."

- **S5 — the chart (PR #8).**
  - **D18 — draw the chart now, defer retry-nudge + natural gap.** *Why:* the data is already measured *and saved*; the figure is the literal deliverable; drawing it forces an honesty check on how the result reads. *Two sub-decisions worth keeping:* **vendoring** the result into a tracked `docs/figures/gap-closure-data.json` (so the figure regenerates after a clean clone — `runs/` is gitignored scratch), and a `test_chart.py` assertion that **pins the vendored data to the D17 numbers** so the figure can't silently drift to plotting something that wasn't measured.

- **S6 — retry-nudge on a new malformed fault (D19, in progress).** *Decision:* build the second guardrail on a fault it can *actually* fix (retry-nudge ↔ malformed call), since against the existing 503 it would measure null. *Design (signed off):* **reject-and-hint**, with two load-bearing properties — **permanent** (so error-recovery ignores it) and **sticky** (so only a *corrected* call clears it; a lucky resend can't). *Honest risk flagged before spending:* GLM may self-correct from the hint in the *baseline* already, making retry-nudge null — handled by a cheap live pilot first, and either outcome is a real finding (a lift, or "GLM self-corrects unaided"). The robust part — **error-recovery ≈ baseline on malformed calls** — holds regardless, demonstrating *guardrail specificity*.

---

## 6. Concepts & vocabulary

| Term (industry name) | One-line meaning | Where it lives here |
|---|---|---|
| **reason→act→observe loop** (agent loop) | decide → run a tool → feed the result back → repeat | `agent.py:128` |
| **tool-calling** (function calling) | model emits a structured call to a named function instead of prose | `scenario.py` schemas; `verify.py` |
| **deterministic oracle / ground truth** | code that knows the right answer and returns PASS/FAIL — never an LLM | `oracle.py` |
| **mechanical vs cognitive failure** | machinery broke (recoverable) vs model genuinely can't reason (not targeted) | thesis; `scenario.py` docstring |
| **fault injection** | deliberately, reproducibly making a tool fail (seeded 503 / malformed call) | `faults.py` |
| **transient vs malformed fault** | call is fine, service hiccups (retry clears it) vs the call itself is wrong (only correction clears it) | `ToolUnavailable` / `MalformedCall` |
| **arm / arm-as-config** | one configuration under test, represented as data (`{label, run_kwargs}`) | `ablation.py:44` |
| **ablation** | toggle one factor on/off, hold all else fixed, attribute the change to it | `ablation.py` |
| **proportion / completion rate** | success is k of N, a fraction — not a normal average | `runner.py` |
| **Wilson interval** | honest CI for *one* proportion; behaves near 0%/100% where ±std breaks | `stats.py:34` |
| **Newcombe interval / straddles-zero gate** | honest CI for the *difference* of two proportions; if it includes 0, "no result" | `stats.py:54`, `:78` |
| **paired comparison** | both arms face the *same* per-trial fault pattern (same seed i) | `ablation.py:67` |
| **kill-trigger** | a pre-agreed "stop and change course" condition, fixed in advance | D10/D12 |
| **harness-level retry vs retry-nudge** | retry by the surrounding code (no model turn) vs re-prompt the model (costs a turn) | `agent.py:101` vs D19 |
| **vendoring** | commit a copy of a gitignored file so the build doesn't depend on scratch | `docs/figures/gap-closure-data.json` |

---

## 7. Recruiter & hiring-manager lens

A reviewer *will* clone this and poke it. Here's the honest two-sided read.

### Reads as a strength
- **Methodological honesty as an artifact, not a footnote.** The pre-registered kill-trigger that *actually fired and was honored*; the `excludes_zero` gate that can return "not a result"; the word **INJECTED** printed on the figure so the caveat travels with the picture. Most candidates would have shipped "67.5% → 100%" as if GLM were naturally that unreliable. This restraint is **senior-level judgment** and is the single most impressive thing here.
- **Genuine statistical literacy.** Wilson + Newcombe (not ±std), with a correct articulation of *why* Wald breaks near the boundaries; the "N = distinct seeds" insight separating reproducibility from statistical power; paired comparison; reporting a 100% bar as its Wilson floor. This is above the bar for most application-engineer candidates.
- **Clean separation of concerns + disciplined restraint.** One job per module; the `Scenario` seam; mechanism-wraps-the-loop. And the discipline to *defer* abstractions (D11) until the second use-case actually exists — explicitly resisting the premature-generalization trap, in writing.
- **Tests that gate the logic offline.** Seven network-free suites (I ran them — all green); a fake-model injection so the loop + CI wiring is tested with **zero API spend**; CI math pinned to hand-computed values; the chart test pinning vendored data to the measured numbers.
- **Decision hygiene + secret/cost hygiene.** ADR-quality decision log with options-weighed-and-why; PR bodies that include the live output and a reproduce command. `.env` gitignored with a committed `.env.example`; the client fails loud on a missing key and never prints it; the `max_tokens` cap is documented as *cost hygiene, explicitly not a reliability mechanism* (a nice tell that the author guards the experiment's cleanliness).

### Reads as a weakness / risk — and how to talk about it
- **The headline is an injected gap (the #1 thing to be ready for).** A skeptic will say: *"You injected 503s, then showed that retrying 503s fixes them — isn't that tautological?"* **Honest framing:** *"Yes, partly — the floor is a controlled testbed, and I say so on the figure. Error-recovery is designed to absorb exactly that fault, so the *direction* isn't surprising. The intellectual content is the measurement discipline — the baseline failed via retry-*exhaustion*, not via the 503 itself, and the contribution is quantifying that *with a gate that could have said 'no effect.' The genuinely novel finding — does this recover GLM's *own* failures — is the natural-gap stretch, and I haven't done it yet."* Owning this pre-empts the probe.
- **Heavy statistics on a narrow measurement.** One task, one target order (ORD-204), one model, one fault type, N=40. A reviewer might read "over-engineered stats for a toy." **Framing:** it's a deliberately legible testbed, and the machinery is built to scale to more arms/faults (S6 is adding the second fault type now) — the binding constraint was always the statistics, so they were built properly first.
- **No CI/CD.** Tests run manually via `uv run test_*.py`; there's no GitHub Actions workflow running them on push, and `check_docs.py` is explicitly "a smoke alarm, not a commit gate." For a project that prides itself on rigor, automated test-on-push is a visible gap. **Cheap to fix — do it before interviews (see §10).**
- **Hand-rolled test harness, not pytest.** Tests use a custom `check()`/`_failures` pattern. It works and adds zero deps, but it's non-standard and a reviewer will notice. **Framing:** a deliberate "no test dependencies for a teaching repo" call — but be ready to say you'd move to pytest for anything shared.
- **Stringly-typed retryability** (`_is_retryable` substring-matches the error). Documented as deliberate (HTTP status signaling is already stringly-typed; it decouples the loop from fault modules), but fragile — a tool whose *legitimate* output contained "retry" could be misclassified. Defensible, worth naming as a known trade-off.
- **Working-tree hygiene right now.** S6 changes sit uncommitted on `main` rather than on `feat/s6-retry-nudge`, which slightly violates the project's own branch-per-change rule. Transient, but a `git status` mid-demo looks messy. **Fix before showing (§10).**
- **Young, solo, short history.** 4 days, one author. The depth-per-day is high and the docs are exceptional, but it's early and small. **Framing:** a learning vehicle built slowly on purpose, with documentation as a first-class output — not a production system, and not pitched as one.

**Bottom line for a hiring manager:** this is a *small* repo that demonstrates *large* judgment — experimental design, statistical honesty, and restraint. Its weaknesses are mostly "young project" (no CI, narrow scope), not "bad engineering." The thing to fix before showing it is the in-progress S6 mess on `main` and the missing CI.

---

## 8. Interview readiness

**Questions a sharp interviewer would ask:**
1. Walk me through the architecture — how does one loop run different tasks *and* different guardrails?
2. Why Wilson + Newcombe instead of mean ± std or a t-test? Why does the textbook interval break here specifically?
3. Your headline is an *injected* gap — isn't that circular? What would make it a genuine finding about GLM?
4. Why is "N = distinct seeds," not "number of runs"? Why does that matter for statistical power?
5. Why a deterministic oracle instead of an LLM judge — and when *would* an LLM judge be acceptable?
6. Error-recovery vs retry-nudge: what's the actual difference, and why build error-recovery first?
7. What breaks at 100× — more arms, a real task, a model you can't injection-control?
8. What's the weakest part, and what would you do differently?

---
**Answer scaffolds (speak from these — all grounded in the repo):**

1. **Architecture.** Task is data (`Scenario`, a frozen dataclass) passed *into* a scenario-agnostic loop; guardrails are toggles *on the loop* (`recover=True`), never edits to the task. Faults wrap the scenario by returning a *new* one (`dataclasses.replace`). So the ablation pushes a byte-identical task through two arms and the only difference is the mechanism → the gap is attributable.
2. **Stats.** A completion rate is a *proportion*, not a normal average. Near 0%/100% with small N, the Wald (±std) interval misbehaves — it can run below 0% or above 100% and understates uncertainty. Wilson is well-behaved at the edges and stays in [0,1]; Newcombe ("square-and-add," method 10) builds the interval *for the difference itself*, which is the number I report. If it straddles 0 I say "no clear effect" — that's the `excludes_zero` gate.
3. **Circularity.** Concede the floor is a controlled testbed (and I label it INJECTED on the figure). The non-trivial bit: the baseline failed by retry-*exhaustion* (`max_steps`), and error-recovery rescues it by moving the retry off the model's turn budget — a real, quantified mechanism effect with a gate that *could* have returned null. The genuinely novel result is the natural-gap stretch (elicit GLM's own failures); it's scoped (D12) but not built — I won't claim it.
4. **Seeds.** With deterministic per-trial seeds, completion is dominated by the fault *pattern*, not GLM's randomness — two N=20 runs failed the identical seeds. So re-running a seed is reproducibility, not new information; power comes from *more distinct* seeds (and a higher fault rate for a bigger gap), not from re-running.
5. **Oracle.** Measuring a small delta needs a fixed ruler. An LLM judge is self-graded homework — its blind spots correlate with the task's, plus flattery and randomness. An LLM judge is acceptable only for genuinely open-ended outputs (summaries, prose quality) where no ground truth exists — and even then you'd calibrate it against humans. Here the answer is a number; exact comparison is the honest choice.
6. **Two retries.** Error-recovery = the *harness* retries a transient failure inside one step, **no** model turn. Retry-nudge = re-prompt the *model* to fix its call, **costs** a turn. Built error-recovery first because S3's gap was 100% retry-exhaustion, which a no-turn-cost retry directly fixes; retry-nudge needs a *malformed* fault to show any lift (that's S6).
7. **Scale.** Adding arms is a list entry + a toggle (arm-as-config) — designed for it. The real limits: the stats need more distinct seeds as effects shrink; the single hardcoded task/order limits generality; and the whole approach assumes you can *inject* faults — on a black-box model with natural failures you'd lose the deterministic fixture (which is exactly why injected faults are the dev floor and the natural gap is the stretch).
8. **Weakest part.** The injected-gap framing limits the headline's reach, and there's no CI yet. I'd add a GitHub Actions run of the offline suites, then prioritize the natural-gap stretch over more injected arms, because that's what turns "I measured my own testbed" into "I measured something about GLM."

---

## 9. Talking points

**Elevator (~30–60s, spoken):**
"forge-gap is a little harness I built to answer one question honestly: when you bolt a reliability guardrail onto a cheaper model running as an agent, *how much* does it actually help — with real error bars? I run a fixed multi-step tool task, grade it with a deterministic checker instead of another AI, and compare a no-help baseline against one guardrail at a time using proper proportion statistics. The twist is the honesty: the model aced my clean task, so there was no gap to measure — and instead of faking one, I inject faults *and say so on the figure itself*, and every claim has to pass a statistical gate that's allowed to come back 'no effect.' The deliverable is one chart: error-recovery closed a +32.5% gap, with a 95% interval that clears zero."

**Deep cut (~2 min, spoken):**
"The decision I'm proudest of is what happened when my plan broke. I'd pre-registered a kill-trigger — *if the model already passes about 85%, stop, there's nothing to measure.* It passed 20 out of 20. So the honest move was to stop and pivot, not to invent a gap. I built a deterministic fault injector — seeded 503 errors in the tools — and reframed the whole thing as a *controlled fault-recovery testbed*, disclosed everywhere, with the natural version kept as a stretch goal. The reason to inject *first* is subtle: you can only unit-test a recovery mechanism if you can reproduce the failure on demand, and a model's natural failures are random. The second decision I'd lead with is statistical: a completion rate is a proportion, so mean-plus-or-minus-standard-deviation is the wrong tool — near 100% it'll hand you an interval above 100%, which is nonsense. I used Wilson intervals per arm and a Newcombe interval on the *difference*, because the difference is the thing I'm actually claiming, so it needs its own error bar — and if that interval includes zero, I'm not allowed to call it a win. That gate is the line between a measurement and a marketing number."

---

## 10. Gaps, debt & next moves

| Priority | Item | Effort | Note |
|---|---|---|---|
| **Now (before showing the repo)** | Land the uncommitted S6 work onto `feat/s6-retry-nudge`; leave `main`'s working tree clean | 5 min | A fresh `git status` here looks mid-surgery; coordinate with the concurrent session (shared worktree). |
| **High** | Add a GitHub Actions workflow running the offline suites on push | ~30 min | Turns "I have tests" into "tests gate the repo" — the cheapest credibility win. |
| **High** | Finish S6: the `nudge` toggle on `agent.run` + the 3-arm experiment, with the de-risking live pilot first | 1 session | The malformed *fault* is built + green; the *mechanism* and the run aren't. Watch the honest-null risk (GLM may self-correct in baseline). |
| **Medium** | The **natural-gap stretch** (D12) | multi-session | The headline prize: measure how much these guardrails recover GLM's *own* failures on a harder task. This is what makes the result a finding about GLM, not just about the testbed. |
| **Low** | Tidy the accumulated `runs/` scratch dirs (gitignored, but cluttered locally); consider pytest for shared use | minor | Cosmetic / convention. |

**Owning the debt out loud is itself a strong signal** — the two things that would most change how this repo reads to a reviewer are (1) clean working tree + CI, and (2) one *natural*-gap arm.

---

## 11. Map of the codebase

| File | What it is |
|---|---|
| `glm.py` | Minimal GLM-via-OpenRouter client (`chat()`, `MODEL`); fails loud on a missing key. |
| `agent.py` | The reason→act→observe loop + grading; the `recover` (error-recovery) toggle and retryability predicate. |
| `scenario.py` | The task as a frozen `Scenario` — chained 2-step lookup + `submit_answer` + ground truth (158). |
| `oracle.py` | Deterministic grader (`grade()`) — exact numeric comparison, never an LLM. |
| `faults.py` | Fault injectors: `with_faults` (transient 503, S3) and `with_malformed_faults` (reject-and-hint, S6). |
| `runner.py` | N-trial single-arm runner (`run_arm`) → raw k/N + every trajectory. |
| `stats.py` | `wilson` (per-arm CI), `newcombe_diff` (gap CI), `excludes_zero` (the honesty gate). |
| `ablation.py` | Two-arm harness (baseline vs +error-recovery) over identical seeds; prints CIs + verdict. |
| `chart.py` | Renders the deliverable PNG from the *saved* numbers — no API. Pure helpers unit-tested. |
| `verify.py` | Smoke test: plain chat + one tool-calling round-trip. |
| `check_docs.py` | Learning-spine freshness check (done stages must be written up). |
| `test_*.py` | Eight offline suites (7 committed + the in-progress `test_malformed.py`); network-free. |
| `docs/ROADMAP.md` · `DECISIONS.md` · `LEARNING.md` | The learning spine: where we are · why we chose what · what it means + glossary. |
| `docs/figures/gap-closure.png` · `…-data.json` | The deliverable figure + its vendored (tracked) source numbers. |
| `pyproject.toml` | `uv` app (not a package); deps: `openai`, `python-dotenv`, `matplotlib`. |

---
*Generated by `/project-guide`. Evidence: full source read, `docs/` spine, git log + 8 merged PRs, the seven offline suites run green during review, and a live read of the in-flight S6 working-tree changes. Where state was mid-change (S6), the guide says so rather than guessing.*
