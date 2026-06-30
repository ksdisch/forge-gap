# forge-gap — Roadmap

**The project in one sentence:** reproduce and *measure* how much specific reliability
guardrails raise a self-hosted model's (GLM-4.6) success rate on a multi-step tool task —
ending in a "gap-closure" chart with honest confidence intervals.

Stages are labelled **S0, S1, S2, …** — each is roughly one build session.

### Phase map — at a glance

```mermaid
flowchart TB
    S0["S0 · Foundation<br/>GLM client + tool-calling smoke test"]:::done
    S1["S1 · Bare agent loop<br/>the no-help baseline"]:::done
    S2["S2 · Real task + oracle<br/>chained lookup · deterministic grading"]:::done
    S3["S3 · Gap diagnostic<br/>20/20 clean → inject faults honestly"]:::done
    S4["S4 · Error-recovery arm + CIs<br/>67.5% → 100% = +32.5% ✓ (a real win)"]:::done
    S5["S5 · Gap-closure chart<br/>the deliverable figure"]:::done
    S6["S6 · Retry-nudge + malformed fault<br/>measured NULL — GLM self-corrects"]:::done
    S7["S7 · Natural-gap hunt · D12<br/>hardened task — GLM aces 8/8, no natural gap"]:::done
    S8["S8 · Weak-model natural gap · D21<br/>submit-nudge: 0% → 75% = +75pp ✓ (mistral-nemo)"]:::done
    F["S9–S12 · planned<br/>validation guardrail / more models"]:::planned

    S0 --> S1 --> S2 --> S3 --> S4 --> S5 --> S6 --> S7 --> S8 --> F

    classDef done fill:#2a9d8f,stroke:#1d6f66,color:#ffffff;
    classDef goal fill:#e9c46a,stroke:#b8902f,color:#222222,stroke-width:2px;
    classDef planned fill:#eeeeee,stroke:#9e9e9e,color:#555555;
```

**Legend:** 🟩 shipped (S0–S8) · ⬜ planned (S9–S12). Key measured outcomes live in the node itself: **S4 = +32.5% ✓** (error-recovery closes the injected gap), **S6 = null** (GLM self-heals malformed calls), **S7 = no natural gap** (a strong model doesn't break on its own — injected faults are required), **S8 = +75 pp ✓** (a *weak* model's natural no-submit gap, closed by a matched submit-nudge while retry-nudge nulls). The detailed table below is the source of truth; this map is its at-a-glance view.

| Stage | What it does (plain English) | Why it exists | Status |
|-------|------------------------------|---------------|--------|
| **S0** | Stands up the foundation: a tiny client (`glm.py`) that talks to GLM-4.6, plus a smoke test (`verify.py`) proving both plain chat **and** tool-calling work. | You can't build an agent until the connection — especially tool-calling — is proven. | ✅ done |
| **S1** | The bare **reason → act → observe** loop (`agent.py`): ask the model what to do, run the tool it asks for, feed the result back, repeat. **Zero** reliability features. | "Build the ugliest working version first." You need a no-help baseline before you can measure how much *any* help adds. | ✅ done |
| **S2** | Swaps the placeholder task for the **real** one: look up an order, look up its zone's shipping rate (a *chained* lookup), add them, submit the total — graded against the known answer (158) by a deterministic **oracle**, never another AI. | Gives the project a real task whose failures are *mechanical* ("called the wrong tool"), not *cognitive* ("bad at math") — the distinction the whole thesis rests on. | ✅ done |
| **S3** | Run that task **many times** on GLM-4.6 and hand-read the trajectories. **Result:** 20/20 — no *natural* gap (kill-trigger 1). Pivot (a *sequence*, not a fork): inject deterministic mechanical faults as the **foundation/floor** (a *controlled fault-recovery testbed*), then later tune harder for a **natural-gap stretch** that reuses the same harness + guardrails (DECISIONS D12). | Proves whether a gap exists and is the *fixable* kind — here the floor is manufactured honestly, with a natural gap as the stretch. Confirmed: rate-0.5 injection → 80% baseline, all-mechanical. | ✅ done |
| **S4** | The **first mechanism arm + the ablation runner**: add a toggleable **error-recovery** guardrail (the harness silently retries a transient tool fault, spending *no* model turn), then run **two arms** — baseline vs +error-recovery — over the *same* injected faults and compute proper confidence intervals (Wilson per arm + Newcombe on the gap between them). | Turns one-off runs into a *measurement of a difference*: the gap-closure number, with honest error bars instead of a bare k/N. | ✅ done — **measured**: 67.5% → 100%, **+32.5%** (Newcombe 95% CI [+17.3%, +48.0%]) at rate 0.6, N=40 |
| **S5** | Draw the **gap-closure chart** — turn S4's two measured arms into the project's headline figure (`chart.py` → `docs/figures/gap-closure.png`): two bars with **Wilson** whiskers, the **Newcombe** gap annotation, and an honesty caption. Reads the *saved* S4 numbers — no re-run. | The actual deliverable, made legible: one honest figure of how much error-recovery closes the injected gap. | ✅ done |
| **S6** | Add the **second guardrail (retry-nudge)** + the **malformed-call** fault it targets, and run a 3-arm ablation (baseline / +error-recovery / +retry-nudge) on that testbed. **Result: a measured NULL** — GLM self-corrects malformed calls unaided, so no guardrail beats the baseline. | Tests *where a guardrail helps* — and finds the boundary: only where the model can't self-correct. | ✅ done |
| **S7** | The **natural-gap hunt** (D12): drop injected faults and *harden the task itself* (a 4–5 lookup chain through ~25 confusable records, named by description so the model must disambiguate) until GLM fails on its own. Pilot-gated, with a bounded escalation. **Result: GLM aced it 8/8 (v1) and 8/8 (v2) — no natural gap.** | Tests the headline goal: does a strong model break on its own merits? It doesn't — so injected faults are the honest way to study guardrails here. | ✅ done — **no natural gap** (4th robustness signal) |
| **S8** | The **weak-model natural-gap** experiment: hold the task fixed and CLEAN, swap GLM-4.6 for a weaker model (`mistral-nemo`), and ablate a NEW **submit-nudge** guardrail (re-prompt a run that stalled without submitting). Pilot-gated; pivoted here after two weak models exposed *non-tool-error* failures. | Tests the **capability × guardrail interaction**: a weak-but-tool-capable model needs a guardrail GLM-4.6 didn't. | ✅ done — **measured**: 0% → 75%, **+75 pp** (Newcombe [+47.8, +88.8]); retry-nudge a null in the same run |
| **S9–S12** | Layer any **further guardrails** (e.g. the parked **validation** guardrail) / fault types / models. | How much *each* guardrail closes the gap. | ⬜ planned |

*(forge-gap runs **S0 → ~S12**; the gap-closure chart now exists at **S5**, and **S6–S12** layer the remaining mechanisms one at a time and extend it — their exact split is still TBD, but the **work items** are fixed even where the numbering isn't. The canonical cross-project tracker is `ACTIVE-PLAN.md` in the separate hub repo; this roadmap is the in-repo view.)*

> **Honesty rule (load-bearing):** the framing is always *"reproduced and measured a known
> primitive — here's the narrow, measured delta,"* never *"I invented this."* If a gap is
> manufactured by injecting faults rather than found naturally, the README/writeup says so.

**Where we are right now:** the S3 diagnostic is done — **GLM-4.6 scored 20/20 (100%)** on the
as-built task, verified genuine (every win used both lookups in the minimal 3 turns; none guessed).
A 100% baseline has nothing for a guardrail to recover, so there's **no natural gap** — the
pre-registered **kill-trigger 1**. Per the plan we don't build guardrails against a non-existent
gap. Instead we treat the two contingencies as a **sequence, not a fork**: **first** inject
deterministic mechanical faults (503-style tool errors) as the **foundation** — a guaranteed,
reproducible gap that also serves as the dev fixture for building the guardrails (the deliverable
**floor**: a *controlled fault-recovery testbed*, stated plainly). **Then**, as a **stretch**, tune
the scenario harder to surface GLM's *own* mechanical failures and re-run the same validated
guardrails for the stronger 'natural gap' result — the harness + mechanisms are shared, only the
fault layer toggles off (DECISIONS D12). The frontier (Claude Sonnet) arm was skipped as moot
(~100%). **Re-diagnosis result:** the injector (`faults.py`) + runner wiring are built and
offline-proven, and the GLM baseline under rate-0.5 injection scored **16/20 = 80%** (vs 100%
clean) — an injected gap that's 100% *mechanical* (all 4 misses are `max_steps` retry-exhaustion)
and recoverable (DECISIONS D13). Confirmed but mild; making it crisp (CIs vs the mechanism arm) is
what S4 builds.

**S4 done — the gap is real, and error-recovery closes it.** Built *and measured*: the
**error-recovery** guardrail (a harness-level `recover` toggle on the loop — it silently re-tries a
transient tool fault *without* spending a model turn), the **Wilson + Newcombe** confidence intervals
(`stats.py`), and the **two-arm ablation harness** (`ablation.py`). The live run at **rate 0.6, N=40
distinct seeds** (GLM-4.6): **baseline 27/40 = 67.5%** (Wilson 95% CI [52.0%, 79.9%]; all 13 misses
were `max_steps` retry-exhaustion) vs **+error-recovery 40/40 = 100%** (Wilson 95% CI [91.2%, 100%];
the harness absorbed **104** transient 503s, spending no model turns). **Gap closed: +32.5%, Newcombe
95% CI [+17.3%, +48.0%]** — the interval clears 0 *and* the two Wilson bars don't overlap, so it's a
real result by our honesty rule. All six offline suites stay green. The choices + measured result are
DECISIONS D14–D17. **Next (S5+):** add retry-nudge as a second arm and draw the gap-closure chart;
the **natural-gap stretch** (D12) remains the bigger prize.

**S5 done — the deliverable figure exists.** The two S4 arms are now drawn as the project's
headline **gap-closure chart** (`chart.py` → `docs/figures/gap-closure.png`): two bars — baseline
**67.5%** vs +error-recovery **100%** — each with its **Wilson 95% CI** as a whisker, the **+32.5%**
gap annotated with its **Newcombe 95% CI [+17.3%, +48.0%]**, and an honesty caption stating the gap
is *injected* (104 transient 503s absorbed). It reads straight from the *saved* S4 numbers (vendored
at `docs/figures/gap-closure-data.json`) — **no re-run, no API** — and regenerates with
`uv run chart.py`. Pure label/format helpers are covered offline by `test_chart.py`; all **seven**
offline suites stay green. The choice + design are DECISIONS **D18**. **Next (S6+):** add
**retry-nudge** as a second mechanism arm — heads-up, against the current 503 faults it will likely
measure **~null** (the bare loop already self-retries), so it only earns a real bar paired with a
failure it actually fixes (e.g. a malformed-call fault — a new `faults.py` type). The
**natural-gap stretch** (D12) is still the headline goal.

**S6 done — the second guardrail measured: a clean NULL (and that *is* the result).** We built the
second guardrail, **retry-nudge** (re-prompt the *model* to fix a failed call — a model turn, vs
error-recovery's no-turn harness retry), plus the fault it targets: a **malformed-call** injector
(`with_malformed_faults`) that rejects the documented parameter with a `400 … use 'id' instead` hint —
*permanent* (so error-recovery structurally can't touch it) and *sticky* (only a corrected call clears
it). A 3-arm ablation on that testbed (GLM-4.6, **N=20, rate 0.6**) measured **baseline 20/20 = 100% ·
+error-recovery 100% · +retry-nudge 100%** (the nudge arm fired **26** corrective re-prompts that changed
nothing) — both gaps **+0.0%**, Newcombe **[−16.1%, +16.1%]**, straddling 0 → **null** by the honesty
gate. The reason is GLM-4.6 itself: it reads the hint *as a tool result* and corrects its own call on the
next turn, so neither guardrail has work to do. The finding *sharpens* S4: a guardrail helps only where
the model **can't help itself** — S4's +32.5% was **turn-exhaustion** recovery, which malformed calls
don't cause. Figure: `docs/figures/malformed-gap.png` (README §8); along the way the machinery generalised
the harness to **N arms** (`run_arms`) and the chart to **N bars**, keeping the S4/S5 figure
byte-compatible. Choices + the measured null are DECISIONS **D19**. All **nine** offline suites green.
**Next (S7+):** the **natural-gap stretch** (D12) — drop injection, harden the task until GLM fails on its
own merits — remains the headline goal, now standing on a richer, two-fault testbed.

**S7 done — the natural-gap hunt: GLM-4.6 doesn't break on its own (a measured no).** The headline stretch
(D12): drop injected faults and *harden the task itself* until GLM fails on its own mechanical merits, then
re-run the guardrails. We built a hardened scenario (`scenario_hard.py`) — a 4-lookup chain (`find_orders` →
`get_order` → `get_ship_rate` → `get_customer_discount`) through 15 look-alike records, named by description so
the model must **disambiguate** — plus a clean, pilot-gated runner (`pilot.py`). **v1 pilot: 8/8 = 100%.** Per a
pre-agreed **bounded escalation** we pushed once more — "hard task v2": a 5-lookup chain (added per-zone tax)
through ~25 records with a near-duplicate-customer distractor ("Globex" vs "Globex Labs") — and got **8/8 =
100%** again, so we **declared done** (the ≥7/8 stop rule fired). Across four probes — 20/20 clean (S3),
self-heals malformed (S6), 8/8 v1, 8/8 v2 — **GLM-4.6 shows no measurable natural gap at reasonable mechanical
difficulty**; studying guardrails on it *requires* injected faults, exactly as S3–S6 did and disclosed. One
load-bearing insight shaped the hunt: the two guardrails only fix *tool-error* failures, but a hard task's
natural failures are mostly *wrong-answer, no-error* (a **validation** gap) which neither can see — so a found
gap would have reopened "build a third guardrail?" rather than rescued the existing two. Choices + the measured
result are DECISIONS **D20**. All **ten** offline suites green. **Next (S8+):** optional — further guardrails /
fault types / models; the project's honest deliverable (the injected gap-closure chart + the S6/S7 boundary
findings) is complete.

**S8 done — a *weak* model has a natural gap, and a matched guardrail closes it (+75 pp).** S7's finding
(GLM-4.6 never breaks naturally) raised the real question: is the *task* unbreakable, or is GLM just strong?
S8 answers it by flipping the variable — hold the task fixed and CLEAN (no injection), swap in a weaker model.
Two fit pilots mapped a **capability cliff**: `llama-3.1-8b` hallucinates a final number even with the data in
hand (a *validation* gap), and `mistral-nemo` computes the right answer (158) but **never calls the terminal
tool** — it narrates "calling submit_answer…" and stops (a *protocol* / no-submit gap). Neither is the
*malformed call* we pre-registered, and neither is visible to the existing arms — so S8 **pivoted** to build a
new, matched guardrail: **submit-nudge** (when a run ends in prose with nothing submitted, re-prompt it to
actually call the tool, then continue). The clean 3-arm ablation on **mistral-nemo, N=20**: **baseline 0/20 ·
+retry-nudge 0/20 (null — it never fires; a no-submit isn't a *failed* call) · +submit-nudge 15/20 = 75%**, gap
**+75.0 pp, Newcombe [+47.8, +88.8]** — clears 0, with non-overlapping Wilson bars: a **real** result. It is the
project's first *natural* (un-injected) gap-closure, and it shows **guardrail specificity** in a single picture —
the wrong guardrail does nothing, the matched one lifts. The residual (5/20 submit `140`, shipping forgotten) is
a *validation* gap submit-nudge can't touch — **parked** as a separate experiment (below). Choices + the measured
result are DECISIONS **D21**; figure `docs/figures/weak-gap.png` (README §9). All **eleven** offline suites green.
**Next (S9+):** the parked validation guardrail; optionally a capability ladder (more models).

**Parked — a future experiment (Kyle's call, 2026-06-30).** The S8 fit pilot found that a weak
tool-capable model (**Llama-3.1-8B**) fails the base task **~100%** on the *clean* task by submitting a
**hallucinated final number even when it retrieved the right data** (twice it submitted the literal
formula string `"item_total_usd + ship_rate"`). That is concrete evidence of the **validation gap** D20/S7
flagged — *wrong-answer, no tool error*, invisible to both error-recovery and retry-nudge. Parked as a
**separate research task**: build a **validation / critic guardrail** (recompute the total from the
retrieved fields; reject a submission that doesn't match) and measure its lift on the Llama-8B testbed.
Distinct from S8 proper, which ladders the *model* up to hunt a *mechanical* natural gap.

> **S3 watch-out — this fired.** The risk was real: GLM-4.6 passed **20/20**, so there's no
> natural gap to measure. We did exactly what this note pre-committed to — **inject faults and say
> so plainly**, now as the *foundation* with a tuned natural gap kept as a *stretch* on top
> (DECISIONS D12) — rather than pretend a natural gap exists.
