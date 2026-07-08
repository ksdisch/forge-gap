# forge-gap — Presenter Pack

Companion to `forge-gap-paper.md`. Purpose: make the author fluent enough to defend the paper claim-by-claim, trace any number to its source file live, and answer the hard questions without over-claiming.

## The one-minute story

I built a measurement harness to answer a question teams usually hand-wave: when you bolt a reliability guardrail onto an LLM agent — a retry, a re-prompt, a validator — how many percentage points does it actually buy? A bare reason→act→observe loop with zero help, a deterministic grader (never an LLM judge), then four guardrails added one at a time, each measured against a baseline with Wilson intervals per arm and a Newcombe interval on the gap — and a pre-registered rule that a gap whose interval straddles zero is a null, reported as one. Headline numbers: harness-level error-recovery closed an **injected** fault gap by **+32.5 pp**; retry-nudge measured a **null** (GLM-4.6 self-corrects); submit-nudge took mistral-nemo from **0% to 75%** on its own natural failure; a self-consistency validator closed the rest — **75% → 100%** on a clean gap, **0% → 45%** on a messy one, with the other 55% hand-decomposed into exactly what a validator structurally can't see. I reproduced known primitives and measured them; I invented nothing — the honesty machinery *is* the deliverable.

## The five claims, and how each is defended

**C1. Error-recovery closes an injected transient-fault gap by +32.5 pp [+17.3, +48.0] (real).**
Defense: the gap is *injected* and every figure says so — that's a feature, not a confession. GLM-4.6 has no natural gap (20/20 clean, 8/8 twice on hardened tasks), so injection was the only reproducible testbed, and reproducible failures are what you develop and unit-test a guardrail against. The mechanism story is verified in trajectories: all 13 baseline misses were `max_steps` retry-exhaustion, the exact failure a no-turn harness retry fixes (104 faults absorbed).

**C2. Retry-nudge measured a null on injected malformed calls (+0.0 pp [−16.1, +16.1]).**
Defense: the null is the finding — GLM-4.6 reads the `400 … use 'id' instead` hint as a tool result and corrects itself next turn; the nudge fired 26 times and changed nothing. The brief pre-committed to publishing either outcome, and no honest tuning could separate the arms (the nudge adds neither information nor turn savings). Bonus control: error-recovery also nulled here, structurally — a permanent fault is never retried.

**C3. Submit-nudge closes a natural no-submit gap: 0% → 75%, +75.0 pp [+47.8, +88.8] (real), while retry-nudge nulls in the same run.**
Defense: the gap is *natural* — clean task, no injection; the weak model computes 158 and just never calls the terminal tool. Retry-nudge fired **zero** times (a missing call isn't a failed call) — an in-experiment negative control that upgrades "submit-nudge works" to "only the *matched* guardrail works." Disclosed caveat: part of the no-submit is the model asking "shall I submit?" and the nudge partly answers "yes."

**C4. Validation (stacked on submit-nudge) closes the residual wrong-answer gap: 75% → 100%, +25.0 pp [+11.1, +40.2] (real).**
Defense: hand-read first — all 5 wrong `140`s in the S8 run had retrieved both inputs and just failed to add, so a self-consistency check is the matched tool. Stacked because the bare baseline never submits (nothing to validate). N=40, not 20, sized in advance with the project's own `stats.py` (N=20 is knife-edge for a ~25 pp effect). Fired on 6/6 wrong submissions ever seen; each became a genuine, model-recomputed 158.

**C5. The same validator on llama-8b's messy gap: 0% → 45%, +45.0 pp [+28.2, +60.2] (real) — and the 55% residual is the measured blind spot.**
Defense: same guardrail byte-for-byte, un-stacked (llama submits unaided). Every miss hand-read: 35% never retrieved the evidence (validator accepts by design — it won't guess), 10% wrong-record retrievals that *fooled* it (self-consistent 152s the oracle still fails), 7.5% non-numeric, 2.5% no-submit. S9 alone would over-sell the check; S10 calibrates it: validation fixes *consistency* failures, never *evidence* failures.

## Provenance table — claim → number → source file

| Claim | Number(s) | Source file |
| --- | --- | --- |
| E1 baseline | 27/40 = 67.5%, Wilson [52.0, 79.9]%; 13 misses all `max_steps` | `docs/figures/gap-closure-data.json` |
| E1 +error-recovery | 40/40 = 100%, Wilson [91.2, 100]%; 104 recoveries | `docs/figures/gap-closure-data.json` |
| E1 gap | +32.5 pp, Newcombe [+17.3, +48.0], excludes zero | `docs/figures/gap-closure-data.json` |
| E2 all three arms | 20/20 = 100%, Wilson [83.9, 100]%; 26 nudges fired | `docs/figures/malformed-gap-data.json` |
| E2 gaps (both) | +0.0 pp, Newcombe [−16.1, +16.1], null | `docs/figures/malformed-gap-data.json` |
| E3 baseline / +retry-nudge | 0/20 and 0/20; nudge fired 0×; 17 no-submit + 3 wrong | `docs/figures/weak-gap-data.json` |
| E3 +submit-nudge | 15/20 = 75%, Wilson [53.1, 88.8]%; +75.0 pp [+47.8, +88.8] | `docs/figures/weak-gap-data.json` |
| E4 reference / +validation | 30/40 = 75% [59.8, 85.8]% / 40/40 = 100% [91.2, 100]%; +25.0 pp [+11.1, +40.2]; 5 fires | `docs/figures/validation-data.json` |
| E4 6/6 conversions; hand-read of S8 trajectories; N-sizing | pilot+full fires all converted; 5 wrong runs all had both inputs | `docs/DECISIONS.md` D22 |
| E5 baseline / +validation | 0/40 [0, 8.8]% / 18/40 = 45% [30.7, 60.2]%; +45.0 pp [+28.2, +60.2]; 20 fires, 17/18 fired-and-corrected | `docs/figures/hallucination-gap-data.json` + D23 |
| E5 residual decomposition | 35% (14/40) never-retrieved · 10% (4/40) wrong-record fooled · 7.5% (3/40) non-numeric · 2.5% (1/40) no-submit | `docs/DECISIONS.md` D23 |
| Capstone: nemo cross-run gap | +100.0 pp, Newcombe [+81.7, +100.0], `cross_run: true` | `docs/figures/capstone-data.json` |
| Capstone: GLM baseline, no guardrail bar | 20/20 = 100% [83.9, 100]%; `guardrails: null` | `docs/figures/capstone-data.json` |
| GLM robustness probes | 20/20 clean (S3); 16/20 at rate 0.5; 8/8 + 8/8 hardened (S7) | `docs/DECISIONS.md` D12, D13, D20 |
| S8 fit pilots / capability cliff | N=8 each, 0/16 combined; nemo no-submit, llama hallucinates | `docs/DECISIONS.md` D21 |
| Validator bright lines | never reads `ground_truth`; re-prompt names components, never the sum | `scenario.py` (`_validate_order_total`), `agent.py` (`_validation_nudge_message`) |
| Stats machinery | Wilson, Newcombe method 10, `excludes_zero` gate | `stats.py` |
| Task & ground truth | 140 + 18 = 158; chained lookup; terminal tool | `scenario.py` |
| Test coverage | 12 offline suites, 77 tests, CI on every PR | `test_*.py`, `.github/workflows/tests.yml` |

## Anticipated questions

**Q: You manufactured your own gap. Isn't the +32.5 a rigged result?**
A: It's a *disclosed, controlled testbed*, not a rigged one — the caption on the figure itself says INJECTED, the fault rate is a published knob, and both arms face identical seeded fault patterns. Injection exists because the honest alternative failed: GLM-4.6 gave us nothing to measure (20/20 clean, 8/8 twice hardened). A reproducible fault is also the only way to unit-test a recovery mechanism. And the natural-gap results (S8–S10) came later with no injection at all.

**Q: Why is a null a result and not a failure of the experiment?**
A: Because the claim gate was fixed before the run and is allowed to say no. The S6 null locates the *boundary* of the thesis — a guardrail pays only where the model can't help itself — and that boundary is what makes the +32.5 interpretable (it was turn-exhaustion recovery, specifically). Burying nulls is how guardrail folklore stays folklore.

**Q: Why Wilson intervals instead of mean ± std? And what's Newcombe?**
A: Completion rate is a proportion. Near 0%/100% with N=20–40, ±std and Wald intervals misbehave — they can escape [0,1] and understate uncertainty, exactly our regime. Wilson stays sane at the edges (a 40/40 arm honestly reads "≥91.2%", not "certainly perfect"). Newcombe's method 10 combines the two arms' Wilson intervals into an interval on the *difference* — the number we actually report — and `excludes_zero` on that interval is the coded "may we claim a result?" gate.

**Q: Isn't the validation guardrail just the answer key hidden inside the agent?**
A: No — two bright lines in code: it never reads `ground_truth` (only the tool results the model itself retrieved this run), and its re-prompt names the components but never the sum. The proof it isn't an answer key: it got *fooled* — in S10 it accepted self-consistent-but-wrong 152s built on the wrong zone's rate, which the oracle then failed. An answer key can't be fooled.

**Q: What exactly is the un-validatable residual?**
A: The 55% of llama's gap a self-consistency check structurally can't recover, hand-read and quantified: 35% never retrieved the shipping rate (nothing to recompute from — the validator accepts rather than guesses), 10% wrong-record retrieval (fooled, as predicted in D22), 7.5% non-numeric submissions, 2.5% no-submit. One-line version: validation fixes consistency failures, never evidence failures.

**Q: Why these three models?**
A: GLM-4.6 was the project's subject; it turned out too strong to fail naturally. To surface *natural* gaps we held the task fixed and lowered only capability. A scout of OpenRouter (254/338 models tool-capable, D21) and two fit pilots picked mistral-nemo and llama-3.1-8b — cheap, canonical, and each failing in a *different*, guardrail-relevant way (no-submit vs hallucination). That difference is what let each guardrail be tested on its matched failure.

**Q: The capstone shows nemo at +100 pp. Was that one experiment?**
A: No — and the figure says so. It's a disclosed *cross-run* gap: the 0/20 baseline is the S8 run, the 40/40 stack is the S9 run. Newcombe on two independent proportions is sound, but it isn't a paired ablation, so it's labeled. Same spirit: GLM gets *no* guardrail bar in the capstone, because no guardrail arm was ever run on its clean task — drawing one would fabricate a measurement.

**Q: What would you do next — and why didn't you?**
A: Two roads, recorded in D24 as *new projects*, not pending stages: a live capability-ladder sweep (same guardrails across more models — the capstone already tells its story from measured data), and a genuinely self-hosted endpoint (llama.cpp/Ollama — the original "Forge" framing; everything here ran via OpenRouter). The project stops on purpose: the story is bracketed at both ends — the strongest model needs no guardrails, and the weakest model's failures are partly beyond any self-consistency check.

**Q: What's the weakest part of the paper?**
A: External validity: one task family, N=20–40, stochastic third-party-hosted models, and no systematic cost accounting (only qualitative spend notes are recorded). Every claim is scoped to this testbed on purpose — the deliverable is the measurement discipline, not a general theory of guardrails.

## Tracing it live

- `uv run chart.py` — regenerates all six figures from the vendored JSONs, no API calls; the capstone JSON is re-derived from the per-stage JSONs on every run.
- Open `docs/figures/<name>-data.json` next to any figure — every bar, whisker, and gap annotation is in the file.
- `uv run pytest` — 77 offline tests, no key needed (CI runs the same on every PR).
- Deep dives: `docs/DECISIONS.md` D12 (inject-and-disclose), D19 (the null), D21 (the pivot), D22 (validator bright lines), D23 (the decomposition), D24 (declared done).
