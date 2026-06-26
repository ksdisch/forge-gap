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
| **S3** | Run that task **many times**, GLM-4.6 vs a frontier model; show GLM fails more often, and hand-read the failures to prove they're mechanical / recoverable. | Proves the two claims everything depends on: a gap exists, and it's the *fixable* kind. | ⏭ next |
| **S4** | The **ablation runner**: automate N trials per "arm" and compute proper confidence intervals (Wilson per arm + Newcombe on the difference). | Turns one-off runs into a *measurement* with error bars. | ⬜ planned |
| **S5–S12** | Layer the **guardrails** one at a time (retry-nudge, error-recovery), optionally inject faults, and draw the **gap-closure chart**. | The actual deliverable: how much each guardrail closes the gap. | ⬜ planned |

*(forge-gap runs **S0 → ~S12**; S5–S12 layer one mechanism at a time and then build the chart — their exact split is still TBD, but the **work items** are fixed even where the numbering isn't. The canonical cross-project tracker is `ACTIVE-PLAN.md` in the separate hub repo; this roadmap is the in-repo view.)*

> **Honesty rule (load-bearing):** the framing is always *"reproduced and measured a known
> primitive — here's the narrow, measured delta,"* never *"I invented this."* If a gap is
> manufactured by injecting faults rather than found naturally, the README/writeup says so.

**Where we are right now:** S2 just merged (PR #1). The scenario grades a single GLM run
PASS/FAIL. Next is S3 — turning one run into a *rate* across many runs, against a stronger model.

> **S3 watch-out (a real risk to the thesis):** today's single run passed on the first try with
> the steps spelled out. If GLM-4.6 turns out to pass ≳85% of the time, there's no gap big enough
> to measure — at which point we make the task harder or inject faults, and **say so plainly**
> rather than pretend a gap exists.
