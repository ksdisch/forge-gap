# forge-gap — Roadmap

**The project in one sentence:** reproduce and *measure* how much specific reliability
guardrails raise a self-hosted model's (GLM-4.6) success rate on a multi-step tool task —
ending in a "gap-closure" chart with honest confidence intervals.

Stages are labelled **S0, S1, S2, …** — each is roughly one build session.

| Stage | What it does (plain English) | Why it exists | Status |
|-------|------------------------------|---------------|--------|
| **S0** | Stands up the foundation: a tiny client (`glm.py`) that talks to GLM-4.6, plus a smoke test (`verify.py`) proving both plain chat **and** tool-calling work. | You can't build an agent until the connection — especially tool-calling — is proven. | ✅ done |
| **S1** | The bare **reason → act → observe** loop (`agent.py`): ask the model what to do, run the tool it asks for, feed the result back, repeat. **Zero** reliability features. | "Build the ugliest working version first." You need a no-help baseline before you can measure how much *any* help adds. | ✅ done |
| **S2** | Swaps the placeholder task for the **real** one: look up an order, look up its zone's shipping rate (a *chained* lookup), add them, submit the total — graded against the known answer (158) by a deterministic **oracle**, never another AI. | Gives the project a real task whose failures are *mechanical* ("called the wrong tool"), not *cognitive* ("bad at math") — the distinction the whole thesis rests on. | ✅ done |
| **S3** | Run that task **many times** on GLM-4.6 and hand-read the trajectories. **Result:** 20/20 — no *natural* gap (kill-trigger 1). Pivot (a *sequence*, not a fork): inject deterministic mechanical faults as the **foundation/floor** (a *controlled fault-recovery testbed*), then later tune harder for a **natural-gap stretch** that reuses the same harness + guardrails (DECISIONS D12). | Proves whether a gap exists and is the *fixable* kind — here the floor is manufactured honestly, with a natural gap as the stretch. Confirmed: rate-0.5 injection → 80% baseline, all-mechanical. | ✅ done |
| **S4** | The **first mechanism arm + the ablation runner**: add a toggleable **error-recovery** guardrail (the harness silently retries a transient tool fault, spending *no* model turn), then run **two arms** — baseline vs +error-recovery — over the *same* injected faults and compute proper confidence intervals (Wilson per arm + Newcombe on the gap between them). | Turns one-off runs into a *measurement of a difference*: the gap-closure number, with honest error bars instead of a bare k/N. | 🚧 code built + offline-green; live measurement pending an API key |
| **S5–S12** | Layer the **remaining guardrails** (e.g. retry-nudge) one at a time, optionally inject faults, and draw the **gap-closure chart** across arms. | The actual deliverable: how much each guardrail closes the gap. | ⬜ planned |

*(forge-gap runs **S0 → ~S12**; S5–S12 layer one mechanism at a time and then build the chart — their exact split is still TBD, but the **work items** are fixed even where the numbering isn't. The canonical cross-project tracker is `ACTIVE-PLAN.md` in the separate hub repo; this roadmap is the in-repo view.)*

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

**S4 status — machinery built, measurement pending.** The S4 code is now built and offline-proven:
the **error-recovery** guardrail (a harness-level retry, added as a `recover` toggle on the loop —
it silently re-tries a transient tool fault *without* spending a model turn), the **Wilson +
Newcombe** confidence intervals (`stats.py`), and the **two-arm ablation harness** (`ablation.py`)
that runs baseline vs +error-recovery over *identical* seeded faults and prints the gap-closure
delta with a straddles-zero / clears-zero verdict. All six offline test suites are green. **What's
left:** the one *live* N-trial measurement — it needs `OPENROUTER_API_KEY`, which isn't in the build
environment — at the recommended operating point **fault-rate 0.6, N=40 distinct seeds**, producing
the actual measured delta + CIs. The choices behind this stage are DECISIONS D14–D16.

> **S3 watch-out — this fired.** The risk was real: GLM-4.6 passed **20/20**, so there's no
> natural gap to measure. We did exactly what this note pre-committed to — **inject faults and say
> so plainly**, now as the *foundation* with a tuned natural gap kept as a *stretch* on top
> (DECISIONS D12) — rather than pretend a natural gap exists.
