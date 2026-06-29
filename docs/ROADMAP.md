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
    G["NEXT — the goal<br/>Natural-gap stretch · D12<br/>harden the task, find GLM's own failures"]:::goal
    F["S7–S12 · planned<br/>further guardrails / fault types"]:::planned

    S0 --> S1 --> S2 --> S3 --> S4 --> S5 --> S6 --> G --> F

    classDef done fill:#2a9d8f,stroke:#1d6f66,color:#ffffff;
    classDef goal fill:#e9c46a,stroke:#b8902f,color:#222222,stroke-width:2px;
    classDef planned fill:#eeeeee,stroke:#9e9e9e,color:#555555;
```

**Legend:** 🟩 shipped (S0–S6) · 🟨 next — the goal · ⬜ planned (S7–S12). Key measured outcomes live in the node itself: **S4 = +32.5% ✓** (error-recovery closes the injected gap), **S6 = null** (GLM self-heals malformed calls, so no guardrail beats baseline). The detailed table below is the source of truth; this map is its at-a-glance view.

| Stage | What it does (plain English) | Why it exists | Status |
|-------|------------------------------|---------------|--------|
| **S0** | Stands up the foundation: a tiny client (`glm.py`) that talks to GLM-4.6, plus a smoke test (`verify.py`) proving both plain chat **and** tool-calling work. | You can't build an agent until the connection — especially tool-calling — is proven. | ✅ done |
| **S1** | The bare **reason → act → observe** loop (`agent.py`): ask the model what to do, run the tool it asks for, feed the result back, repeat. **Zero** reliability features. | "Build the ugliest working version first." You need a no-help baseline before you can measure how much *any* help adds. | ✅ done |
| **S2** | Swaps the placeholder task for the **real** one: look up an order, look up its zone's shipping rate (a *chained* lookup), add them, submit the total — graded against the known answer (158) by a deterministic **oracle**, never another AI. | Gives the project a real task whose failures are *mechanical* ("called the wrong tool"), not *cognitive* ("bad at math") — the distinction the whole thesis rests on. | ✅ done |
| **S3** | Run that task **many times** on GLM-4.6 and hand-read the trajectories. **Result:** 20/20 — no *natural* gap (kill-trigger 1). Pivot (a *sequence*, not a fork): inject deterministic mechanical faults as the **foundation/floor** (a *controlled fault-recovery testbed*), then later tune harder for a **natural-gap stretch** that reuses the same harness + guardrails (DECISIONS D12). | Proves whether a gap exists and is the *fixable* kind — here the floor is manufactured honestly, with a natural gap as the stretch. Confirmed: rate-0.5 injection → 80% baseline, all-mechanical. | ✅ done |
| **S4** | The **first mechanism arm + the ablation runner**: add a toggleable **error-recovery** guardrail (the harness silently retries a transient tool fault, spending *no* model turn), then run **two arms** — baseline vs +error-recovery — over the *same* injected faults and compute proper confidence intervals (Wilson per arm + Newcombe on the gap between them). | Turns one-off runs into a *measurement of a difference*: the gap-closure number, with honest error bars instead of a bare k/N. | ✅ done — **measured**: 67.5% → 100%, **+32.5%** (Newcombe 95% CI [+17.3%, +48.0%]) at rate 0.6, N=40 |
| **S5** | Draw the **gap-closure chart** — turn S4's two measured arms into the project's headline figure (`chart.py` → `docs/figures/gap-closure.png`): two bars with **Wilson** whiskers, the **Newcombe** gap annotation, and an honesty caption. Reads the *saved* S4 numbers — no re-run. | The actual deliverable, made legible: one honest figure of how much error-recovery closes the injected gap. | ✅ done |
| **S6** | Add the **second guardrail (retry-nudge)** + the **malformed-call** fault it targets, and run a 3-arm ablation (baseline / +error-recovery / +retry-nudge) on that testbed. **Result: a measured NULL** — GLM self-corrects malformed calls unaided, so no guardrail beats the baseline. | Tests *where a guardrail helps* — and finds the boundary: only where the model can't self-correct. | ✅ done |
| **S7–S12** | Layer any **further guardrails** / fault types, or pursue the **natural-gap stretch** (D12). | How much *each* guardrail closes the gap. | ⬜ planned |

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

> **S3 watch-out — this fired.** The risk was real: GLM-4.6 passed **20/20**, so there's no
> natural gap to measure. We did exactly what this note pre-committed to — **inject faults and say
> so plainly**, now as the *foundation* with a tuned natural gap kept as a *stretch* on top
> (DECISIONS D12) — rather than pretend a natural gap exists.
