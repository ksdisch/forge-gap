# Session log — forge-gap S8: weak-model natural gap + submit-nudge (2026-06-30)

Merged as **PR #14** (merge `8667256`, work `8d7605d`). All 11 offline suites green; `check_docs` passes.

## 1. What we did
- Opened S8 with a start-of-stage decision brief (**D21**); scouted OpenRouter (254/338 models are tool-capable); Kyle signed off on **weak model = `mistralai/mistral-nemo`** + **MVP scope**.
- Two **fit pilots** (N=8, clean) mapped a **capability cliff**: `llama-3.1-8b` hallucinates the final number even with the data in hand (validation gap); `mistral-nemo` computes `158` but **never calls `submit_answer`** (no-submit / protocol gap). Both 0/16 — neither the pre-registered *malformed call*.
- **Pivoted** (Kyle-approved): built a NEW **submit-nudge** guardrail (TDD — `test_submit_nudge.py` red→green in `agent.py`), wired `submit_nudges` through `runner.py` + `ablation.py` (`SUBMIT_NUDGE_ARM`).
- Built `weak_ablation.py` (clean 3-arm harness, `fault_kind="none"`); pilot N=8 confirmed the lift; ran full **N=20**.
- **Result**: baseline 0/20 · +retry-nudge 0/20 (**null**, fired 0×) · **+submit-nudge 15/20 = 75%**, gap **+75.0 pp, Newcombe [+47.8, +88.8]** — REAL, non-overlapping Wilson bars. First *natural* (un-injected) gap-closure.
- Parameterized `chart.build_multi_figure` (`caption_fn`/`subtitle`) for an honest **NATURAL** caption → `docs/figures/weak-gap.png` + vendored data + `test_chart` coverage. Added `glm.py max_retries=8` (a provider 429 aborted a pilot mid-run).
- Spine: **D21**, ROADMAP **S8** + a **Parked** validation-guardrail note, LEARNING **S8** (+ glossary), README §9, CLAUDE.md. Saved a memory (`runs/` stale-trajectory gotcha).

## 2. The why
- **Swap the model, not the task.** S7 proved GLM-4.6 never breaks and that *hardening the task* nulled. The honest way to surface a natural gap is to lower the one variable — model capability — while holding the task fixed. That *is* the ablation; the claim is the **capability × guardrail interaction**, not "GLM needs guardrails." Rejected: more task-hardening (S7 already showed it nulls, and it manufactures off-thesis cognitive failures).
- **Pilot-gate before building** (project rule D6: prove a gap exists *and is the right type* first). The N=8 pilots caught that neither weak model fails by malformed call — saving a full run of the wrong arms.
- **Pivot to the observed failure.** The data showed a *no-submit* gap; retry-nudge fires only on a *failed* call, so it structurally can't see it. We built the guardrail that matches the failure we saw, not the one we planned. Rejected: keep laddering models (two bifurcations → low value); pull the validation guardrail forward (bigger, noisier — parked per Kyle).
- **Keep retry-nudge as a negative control.** Running the *wrong* guardrail in the same experiment (expected null) turns "submit-nudge works" into the sharper "only the *matched* guardrail works" — guardrail specificity, made visible, for cheap.
- **Parameterize the chart, don't fork it.** `build_multi_figure` hardcoded an "INJECTED malformed" caption; passing `caption_fn`/`subtitle` keeps the S6 figure byte-compatible while letting S8's caption honestly say NATURAL. Additive, not a rewrite.
- **Name infra as infra.** `max_retries=8` rides out provider 429s but is commented as HTTP-layer hygiene, explicitly *not* the experiment's `recover` arm (which retries *tool* faults) — so it can't be misread as a measured mechanism.

## 3. Concepts and vocabulary
- **submit-nudge** — re-prompt a run that ended in prose without submitting, to call the terminal tool (the S8 `submit_nudge` toggle in `agent.py`).
- **protocol gap / no-submit** — model has the right answer but never emits the terminal tool call; ends in prose. mistral-nemo's natural failure.
- **validation gap** — model submits a *wrong number with no error* (dropped a term / wrong field). The residual `140`s; the parked next experiment.
- **guardrail specificity** — a guardrail closes one named failure and is blind to the rest; today retry-nudge nulled while submit-nudge lifted, in the same run.
- **capability cliff / bifurcation** — models cluster at extremes (ace vs ~0%); two weak models both failed 0% but in two *different* ways. Triggered the pivot.
- **capability × guardrail interaction** — how much a guardrail helps depends on the model's capability; the S8 thesis (submit-nudge is worthless on GLM, +75 pp on mistral-nemo).
- **Wilson / Newcombe intervals** — Wilson = CI for one proportion (an arm's rate); Newcombe = CI for the *difference* between two arms. Straddles 0 = null (the honesty gate).
- **fit pilot** — a tiny baseline-only run to check a model lands in the measurable band (not ~100%, not ~0%) before a full ablation.
- **negative control** — a condition you *expect* to show no effect (retry-nudge here; `recover` on a clean task). If it moves, something leaked in.
- **vendoring** — committing a copy of a gitignored artifact (the runs summary → `docs/figures/weak-gap-data.json`) so the figure rebuilds offline.

## 4. Takeaways
- **Let the pilot re-point the experiment.** The pre-registered malformed-call arm was worthless; the pilots showed a no-submit gap, so we built the matched guardrail instead. Cheap probes beat committing to a plan.
- **Ship the wrong guardrail on purpose.** A null-by-design control (retry-nudge) in the same chart upgrades the claim from "X works" to "only the *matched* guardrail works" — a stronger, harder-to-dispute result for free.
- **Change one variable to isolate a cause.** Holding the task fixed and swapping only the model is what makes the gap attributable to capability, not difficulty.
- **Label infra hygiene as infra.** `max_retries=8` prevents a 429 from aborting an arm, but naming it HTTP-layer keeps it from masquerading as a measured mechanism.

## 5. Suggested next moves
- **(Recommended) Validation guardrail (S9)** — the parked experiment: recompute the total from the model's *retrieved tool results* and reject a mismatch (a process/self-consistency check, **not** peeking at the oracle's ground truth). Targets the residual `140`/hallucination failures neither existing guardrail sees. *Why:* completes the "each failure type → its own guardrail" story on the exact residual S8 left; opens with a **D22** brief for sign-off. *Effort:* ~1 session (one real design call + a focused TDD build, like submit-nudge).
- **Capability ladder** — run `weak_ablation.py` across 2–3 models (e.g. mistral-nemo / a mid model / GLM-4.6 as the 100% ceiling) for a lift-vs-capability curve. *Why:* a richer "when does a guardrail matter" story; mechanical reuse of the harness. *Effort:* ~half session (mostly live runs + a curve chart).
- **Per-trial resilience in `run_arm`** — wrap `run_fn` in try/except so a provider error skips/retries one trial instead of aborting the whole arm. *Why:* the 429 abort was luck-of-the-draw; a bigger-N run is exposed even with `max_retries=8`. *Effort:* small; do it if the ladder needs many trials.

## 6. 30-second elevator version
Today I closed out stage eight of forge-gap, a harness that measures how much reliability guardrails help a model finish a multi-step tool task. Earlier stages showed a strong model never fails on its own, so I flipped the variable — kept the task fixed and clean, and swapped in a weaker model. It turned out that model computes the right answer but often forgets to actually call the tool that submits it, so I built a new guardrail called submit-nudge that re-prompts it to submit — and completion jumped from zero to seventy-five percent, with tight confidence intervals. The nice part: I ran the *wrong* guardrail in the same experiment and it did literally nothing, which proves a guardrail only helps when it matches the specific failure. It's the project's first natural, un-injected result, and it's merged.

## 7. Active recall
Q1. Walk me through why retry-nudge measured an exact 0.0 pp gap while submit-nudge lifted completion 75 pp — both re-prompt the model.
Q2. Why swap the model instead of hardening the task further to find a natural gap? What does that buy you?
Q3. submit-nudge got the model to submit every time, but completion was 75%, not 100%. What's the missing 25%, and why can't submit-nudge fix it?
Q4. You added `max_retries=8` to the client mid-experiment. Why is that *not* a "reliability mechanism" the way error-recovery is?
Q5. What's the point of keeping retry-nudge — a guardrail you expected to fail — in the final 3-arm chart?

---
Try to answer each aloud before scrolling. Answer key below.

### Answer key
**A1.** Trigger mismatch. Retry-nudge fires only after a *failed tool call*. mistral-nemo's failure is a *missing* call — it computes 158 and ends in prose without calling `submit_answer`, so there's no failed call to trigger on (it fired 0 times). Submit-nudge fires on exactly that condition (ended without submitting) and re-prompts the model to make the call. Same idea, different trigger; only the trigger matching the failure helps.

**A2.** Hardening the task was S7 and it nulled (GLM aced it) — and a strong model's natural failures tend to be cognitive or wrong-answer, off-thesis. Swapping the model changes the ONE variable (capability) while holding the task fixed, so any gap is attributable to capability, not task difficulty. It also frames the claim honestly: the *interaction* between capability and guardrail, not "this model is bad."

**A3.** The missing 25% is a *validation* gap: mistral-nemo sometimes submits `140` — the item total with shipping forgotten — a wrong answer with no error. Submit-nudge makes the model *submit*; it can't make the arithmetic *right*. Fixing it needs a validation guardrail (recompute from the retrieved fields and reject a mismatch), which is the parked next experiment.

**A4.** `max_retries=8` retries the *HTTP call to the provider* on a 429/5xx — infrastructure flakiness unrelated to the model's task behavior. error-recovery retries a *tool* fault inside the agent loop and is a measured arm whose effect on completion we report. Conflating them would let infra hygiene masquerade as a guardrail result; it's commented as HTTP-layer to keep that line clean.

**A5.** It's a negative control. Running the wrong guardrail (retry-nudge) beside the right one (submit-nudge) shows it does nothing on this failure — turning "submit-nudge helps" into the sharper "only the *matched* guardrail helps." It also guards against a harness artifact silently inflating every arm.
