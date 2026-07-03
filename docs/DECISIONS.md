# forge-gap — Decision Log

Every real choice in the project: what we picked, the options we weighed, and why. Plain
English. **This is where you weigh in** — if a "why" doesn't convince you, that's a
conversation, not a closed door.

*(Engineers sometimes call these "ADRs" — Architecture Decision Records. Ignore the acronym;
it just means "what we decided and why, written down so future-you isn't confused.")*

---

## D1 — Framing: "reproduce and measure," never "invent"
- **The choice:** present forge-gap as *reproducing a known reliability primitive and measuring
  its effect*, not inventing something new.
- **Options weighed:** (a) honest reproduction ✅ · (b) dress it up as a novel technique.
- **Why:** credibility. The defensible claim is a *clean measurement* ("this guardrail adds
  X%, ± this much"). Overclaiming novelty is both untrue and easy to puncture.

## D2 — Grade with a deterministic oracle, NOT an AI judge ⭐
- **The choice:** a plain-Python function (`oracle.py`) checks the model's submitted number
  against a known-correct answer (158). Pass/fail is mechanical equality.
- **Options weighed:** (a) deterministic oracle ✅ · (b) ask another AI ("LLM judge") whether
  the answer looks right.
- **Why:** an AI judge is *self-graded homework* — you'd ask the same kind of system that can
  fail the task to score it, so its blind spots line up with the task's, and it adds flattery +
  randomness. Measuring a *small* difference needs a fixed ruler, not a rubber one.
- **Plain-English terms:** *oracle* = code that already knows the right answer and says
  pass/fail. *ground truth* = that known-correct answer.

## D3 — Make failures MECHANICAL, not COGNITIVE ⭐
- **The choice:** the task is a **chained two-step lookup** with **trivial arithmetic** (one
  addition). The model must thread a value from step 1 (the order's zone) into step 2 (look up
  that zone's rate).
- **Options weighed:** (a) chained lookup + trivial math ✅ · (b) two *independent* lookups + a
  sum (rejected — too easy, risks no measurable gap) · (c) a salary-÷-budget style task (rejected
  — its difficulty *is* the arithmetic, so it manufactures *cognitive* failures, the wrong kind).
- **Why:** the whole thesis is that GLM's failures are *mechanical* (wrong tool, wrong field,
  skipped step) and therefore **recoverable** by a guardrail — not *cognitive* (genuinely can't
  do the math). Hard arithmetic would manufacture the wrong kind of failure.
- **Plain-English terms:** *mechanical failure* = the machinery of a step broke (bad call, wrong
  record). *cognitive failure* = the model genuinely couldn't reason it out.

## D4 — Capture the answer with a `submit_answer` terminal tool
- **The choice:** the model finishes by *calling a tool* `submit_answer(value)`; the loop reads
  the structured number. It never scrapes prose for "the answer."
- **Options weighed:** (a) structured terminal tool ✅ · (b) pull a number out of the model's
  text reply.
- **Why:** a missing or botched submit becomes a *clean, classifiable* mechanical failure
  (exactly what S3 triages), and the oracle grades a real number, not a guess at what the prose
  meant. Parsing prose would add its own errors and blur the measurement.
- **Plain-English term:** *terminal tool* = a special tool whose only job is to end the task and
  hand over the final answer.

## D5 — Run at temperature 0.7; get signal from N, not from temp 0
- **The choice:** run the model with `temperature = 0.7` and always record it.
- **Options weighed:** (a) temp 0.7 + many runs ✅ · (b) temp 0 to chase a single repeatable run.
- **Why:** GLM is *stochastic* (a little random) regardless, so temp 0 would fake a determinism
  that isn't real. The honest fix is sample size: run it many times and report a *rate* with
  error bars.
- **Plain-English terms:** *temperature* = a knob for how random the model's output is (0 = most
  predictable). *stochastic* = involves randomness, so the same input can give different outputs.

## D6 — Baseline first: zero mechanisms before any guardrail
- **The choice:** S1's loop has **no** retry, no recovery, no validation. Guardrails come later,
  one at a time.
- **Options weighed:** (a) bare baseline first ✅ · (b) build the guardrails up front.
- **Why:** you can't measure how much a guardrail *helps* without a no-help baseline to compare
  against. The bareness is the experiment's control group.
- **Plain-English terms:** *baseline* = the no-help version you measure improvements against.
  *guardrail / mechanism* = a reliability feature (e.g. "if a call is malformed, nudge the model
  to retry").

## D7 — Measure with proportion confidence intervals; report overlaps as null *(planned)*
- **The choice:** success is a *proportion* (X passes out of N). Use **Wilson** intervals for
  each arm and a **Newcombe** interval for the *difference* between arms. If two bars' ranges
  overlap, report "no clear effect," not a win.
- **Options weighed:** (a) proper proportion CIs ✅ · (b) plain mean ± standard deviation.
- **Why:** a pass/fail rate isn't a normal "average," so ±std is the wrong tool and would
  over-claim. The binding constraint on this project is the *statistics* (noise), not the code.
- **Status:** built in S4 — `stats.py` (`wilson`, `newcombe_diff`, `excludes_zero`); see D16 for the implementation specifics.
- **Plain-English terms:** *proportion* = a fraction of successes. *confidence interval* = the
  honest range the true rate likely sits in, given only N samples.

## D8 — Split into `scenario.py` (task) / `oracle.py` (grader) / `agent.py` (engine)
- **The choice:** the task-as-data lives in `scenario.py`, the grader in `oracle.py`, and the
  reusable loop in `agent.py`. The `Scenario` bundle is the seam between them.
- **Options weighed:** (a) three focused modules around a `Scenario` bundle ✅ · (b) keep the task
  hardcoded inside `agent.py`.
- **Why:** the coming S4 ablation runner has to push the *same* task through the loop under
  different guardrail "arms" — so the task must be a value you can pass in, while the mechanisms
  wrap the *loop*. Introducing that bundle now isn't premature: `agent.py`'s own earlier docstring
  already anticipated the swap, so the seam was real, not speculative.
- **Plain-English terms:** *parameter object* = bundling several related values into one passed-in
  object instead of many loose arguments. *the natural seam* = the place the code was already going
  to split anyway.

---

## D9 — Frontier comparison arm = a current frontier model (Claude Sonnet)
- **The choice:** the "is there a gap?" check runs the *same* task on a strong frontier model —
  **Claude Sonnet** — as the reference line against GLM-4.6.
- **Options weighed:** (a) Claude Sonnet ✅ · (b) GPT (OpenAI) · (c) Gemini 2.5 Pro.
- **Why:** all three near-certainly pass this deliberately-easy two-step task, so the pick barely
  moves the measurement — its real job is to prove the task is *doable*, which is what lets us call
  GLM's failures *mechanical* (the machinery slipped) rather than "the task is impossible." Claude
  Sonnet gives a reliable, crisp ~100% ceiling at trivial cost.
- **Plain-English term:** *arm* = one configuration under test (here, one model); later "+retry"
  vs "baseline" will be arms too.

## D10 — S3 sequencing: GLM-first, then frontier (operationalizing kill-trigger 1)
- **The choice:** run GLM-4.6 @ N=20 first, **stop and read** the rate, then run the frontier arm
  only if a gap looks plausible.
- **Options weighed:** (a) GLM-first, pause, then frontier ✅ · (b) run both arms at once.
- **Why:** the whole stage hinges on "does a gap exist?" If GLM already passes ≳85% there's no
  headroom for a guardrail to show a measurable lift (kill-trigger 1), and we'd pivot — make the
  task harder or inject faults — *before* spending the frontier run. GLM-first early-outs when
  there's no gap and loses nothing when there is.
- **Plain-English term:** *kill-trigger* = a pre-agreed "stop and change course" condition, fixed
  in advance so we can't rationalize past a result we don't like.

## D11 — The S3 runner is a lean *diagnostic*, not the S4 ablation harness
- **The choice:** `runner.py` only loops the task N times for a given `(model, N, label)` and
  reports the raw k/N completion rate, keeping every trajectory. **No** confidence intervals, **no**
  guardrail toggles yet.
- **Options weighed:** (a) lean diagnostic now, generalize at S4 ✅ · (b) build the full ablation
  runner (arms-as-config + Wilson/Newcombe CIs) up front.
- **Why:** S3's only job is to answer "is there a mechanical gap worth closing?" — raw rates plus
  hand-read transcripts answer that. CIs (D7) and guardrail arms are the S4 generalization; building
  them now is the premature-abstraction trap (cf. D8 — parameterize at the *natural seam*, and the
  seam for arms-as-config only appears at S4, when a second arm-*type* actually exists).

## D12 — Kill-trigger 1 fired → inject faults as the *foundation*, tune for a natural gap as the *stretch* ⭐
- **The finding:** GLM-4.6 completed the as-built task **20/20 (100%)** — verified genuine (every
  win used both lookups in the minimal 3 turns; none guessed "158"). With S2 + the smoke run that's
  22/22, zero failures. A baseline at 100% has *nothing* for a guardrail to recover, so there is no
  natural gap to measure. This is the pre-registered **kill-trigger 1**.
- **The choice:** treat the two contingencies as a *sequence*, not a fork. **First** build a
  deterministic mechanical-fault injector (503-style transient tool errors in the lookup tools) — it
  manufactures a guaranteed, reproducible gap *and* doubles as the dev fixture for building the
  guardrails. **Then**, as a stretch, tune the scenario harder to elicit GLM's *own* mechanical
  failures and re-run the same, already-validated guardrails for the stronger 'natural gap' result.
- **Options weighed:** (a) inject-first, then tune — as a sequence ✅ · (b) inject only (the
  controlled testbed as the whole deliverable) · (c) tune-first for a natural gap, no injector ·
  (d) document the null and stop.
- **Why inject *first* (a stepping stone, not a detour):** you can only *develop and unit-test* a
  recovery mechanism if you can **reproduce the failure on demand** — and GLM's natural failures are
  stochastic, so they can't be a deterministic test. Injected faults are that reproducible fixture,
  giving a guaranteed deliverable **floor** (a guardrail provably recovers the failure it targets,
  by X% ± CI). The measurement harness *and* the guardrail mechanisms built here are then **reused**
  by the natural-gap stretch — only the fault layer toggles off. Tuning first risks burning effort
  chasing an uncertain gap before the mechanisms even exist.
- **The honesty caveat (load-bearing):** we always disclose which gap is which. The **floor**
  headline is a *controlled fault-recovery testbed* — gap injected, fault rate a published knob, no
  hidden thumb on the scale. **If** the tuned natural gap materializes, the headline strengthens to
  'guardrails recover both injected faults *and* GLM's real failures on a harder task,' with the
  natural arm labeled as natural. We never claim a natural gap we didn't actually observe.
- **The hand-off caveat:** injected faults (the tool *errors*) are a clean *subset* of natural
  failures. Some natural failures — silently grabbing the wrong record (no error fires) or never
  submitting — won't be caught by retry/error-recovery and would want different guardrails. So the
  natural-gap stretch measures *how much of GLM's real failure surface* these mechanisms cover, and
  reports honestly what's left over.
- **Plain-English terms:** *fault injection* = deliberately, reproducibly making a tool fail
  sometimes (here a 503-style "temporarily unavailable" error) so there's a recoverable failure to
  measure guardrails against. *transient error* = one that may succeed if you simply retry. *dev
  fixture* = a controlled, repeatable setup you build and test your code against.

## D13 — S3 re-diagnosis: the injected gap is real, mechanical, and (for now) mild
- **The result:** the GLM baseline under rate-0.5 injection scored **16/20 = 80%** (vs 100% clean).
  All 4 failures were `max_steps` — GLM persistently retried the 503'd tool but exhausted its
  6-step budget (e.g. seed 4: `get_order` 503'd all six steps). **100% mechanical** (retry-
  exhaustion), 0% cognitive, and recoverable — a harness-level retry that doesn't consume model
  turns would rescue them. That's exactly the failure the S4 error-recovery arm targets.
- **The sampling insight (load-bearing):** with deterministic per-trial seeds (0..N-1), completion
  is dominated by the fault *pattern*, not GLM's stochasticity — two independent N=20 runs failed
  the *identical* seeds {4, 9, 16, 18}. So **"N" = the number of distinct seeds**; re-running the
  same seeds is reproducibility, not more data (don't pool two 20-seed runs into "N=40"). More
  statistical power = more *distinct* seeds.
- **Crispness (for the S4 chart):** 80% vs a projected ~100% mechanism arm would have *overlapping*
  Wilson CIs at N=20 → "not a result" (the honesty rule). The knobs, deferred to S4–S6: raise the
  fault rate (bigger gap) and/or scale distinct seeds toward N=50 (tighter CIs).
- **Net:** S3's job is done — the injected gap exists, is mechanical, and is recoverable. Building
  the recovery mechanism (error-recovery) + the Wilson/Newcombe CIs is S4.
- **Plain-English term:** *Wilson confidence interval* = the honest range a true pass-rate sits in
  given only N samples; if two bars' ranges overlap, you can't claim one really beat the other.

---

## D14 — S4 scope = the first mechanism arm (error-recovery), folded in with the CIs ⭐
- **The choice:** make S4 the *first reliability-mechanism arm* — **error-recovery** — built together
  with the confidence intervals, not CIs-only with all mechanisms deferred to S5+. This also
  reconciles a numbering mismatch: the in-repo roadmap had called S4 "the ablation runner + CIs,"
  while the cross-project plan (and this branch's name, `…s4-mechanism…`) fold the first mechanism
  into S4. We adopt the latter; the full multi-mechanism *chart* stays S5+.
- **Which mechanism first — the real fork:** **error-recovery** before retry-nudge.
  - *error-recovery* = the **harness** retries a failed tool call transparently, inside the same
    step, spending **no** model turn.
  - *retry-nudge* = we re-prompt the **model** to try again — which still **costs** a turn.
- **Options weighed:** (a) error-recovery first ✅ · (b) retry-nudge first (the cross-project plan's
  order) · (c) build both arms this stage.
- **Why error-recovery first:** S3's gap is 100% `max_steps` *retry-exhaustion* — GLM already
  re-tries the 503'd tool on its own, and each retry burns one of its 6 turns until it runs out. The
  guardrail that actually rescues that is a retry which *doesn't* consume turns — i.e.
  error-recovery. Retry-nudge, against this exact failure, would likely measure ~null (it just
  formalises what the bare loop already does). So error-recovery is the highest-information first
  arm. Retry-nudge stays a clean S5 sibling — the loop's `recover` flag is built so adding
  retry-nudge is one more toggle, not a rewrite.
- **Process note (honest):** this *reverses* the cross-project plan's ordering, so it was surfaced
  as a sign-off question rather than assumed. The interactive prompt couldn't be delivered in the
  build environment; because the choice is **additive and reversible** (error-recovery is needed for
  the chart no matter what, and retry-nudge can be added later), we proceeded on the recommended
  order and left it trivial to redirect. Flagged, not silently overridden.
- **Plain-English terms:** *arm* = one configuration under test (baseline vs +mechanism). *toggle* =
  a single on/off switch (here `recover=True`). *additive change* = one that only adds, so it can't
  break or undo what's already there.

## D15 — Crispness operating point is a runtime knob; recommended fault-rate 0.6, N=40
- **The choice:** don't hard-code the fault rate or N. Keep **both as command-line arguments** to
  `ablation.py`, and set the *recommended* operating point to **fault-rate 0.6, N=40 distinct
  seeds**. (S3 ran rate 0.5, N=20.)
- **Options weighed:** (a) rate 0.6 / N=40 recommended but parameterised ✅ · (b) reuse rate 0.5 /
  N=20 (S3's point) · (c) push to rate 0.7 / N=50.
- **Why:** S3's 80%-vs-~100% at N=20 gives *overlapping* Wilson intervals → "not a result" by the
  honesty rule (D7). A bigger gap (a lower baseline) plus more seeds (tighter bars) is what clears
  the interval. Rate ~0.6 targets a ~55–65% baseline (headroom for the mechanism to rise into), and
  N=40 meaningfully tightens the CI without doubling the cost twice over. Leaving them as knobs means
  the operating point can be retuned run-to-run without touching code — the binding constraint here
  is the statistics, not the code (D7), so tuning must stay cheap.
- **The seed rule (reaffirmed from D13):** "N" = the number of **distinct** seeds (0..N−1). Both arms
  run seed i against the *same* `with_faults(seed=i)` scenario, so it's a **paired** comparison on an
  identical fault pattern; re-running a seed is reproducibility, not more data.
- **Plain-English terms:** *operating point* = the specific (fault-rate, N) you choose to run at.
  *paired comparison* = both arms face the same fault pattern per trial, so the gap between them isn't
  muddied by one arm simply getting easier faults.

## D16 — The CIs: Wilson per arm, Newcombe on the gap, straddles-zero is the honesty gate
- **The choice:** implement D7 in `stats.py`. Each arm's rate gets a **Wilson** interval; the
  *difference* between arms gets a **Newcombe** interval (his "square-and-add" method 10, which
  combines the two arms' Wilson intervals); `excludes_zero(lo, hi)` is the gate that decides whether
  we may claim an effect at all.
- **Options weighed (for the *difference* interval):** (a) Newcombe square-and-add ✅ · (b) a
  normal-approximation (Wald) difference interval · (c) just draw two separate Wilson bars and
  eyeball whether they overlap.
- **Why:** a completion rate is a *proportion*, and near 0%/100% with small N the textbook Wald
  interval misbehaves — it can run outside [0, 1] and understate the uncertainty, exactly our regime.
  Wilson stays sane at the edges; Newcombe carries that good edge-behaviour into the *difference*,
  which is the number we actually report. Eyeballing two Wilson bars (c) is a fine gut-check but
  isn't a real difference test — bars that merely touch can still hide a real effect (or a null), so
  we compute the difference interval directly.
- **The gate (load-bearing):** if the Newcombe interval includes 0, the arms are statistically
  indistinguishable at this N → we report "no clear effect," never a win. This mechanises D7's
  honesty rule instead of leaving it to judgement.
- **Design — paired arms in `ablation.py`:** arms are *config* (`{label, run_kwargs}`), and the
  harness runs both over one shared `make_scenario(i)`. D11 said arms-as-config should arrive at S4,
  at the natural seam — it does, now that a second arm-*type* actually exists. The mechanism wraps the
  **loop** (a `recover` flag threaded through `run_arm`'s new `run_kwargs`), never the task (D8): the
  `Scenario` is byte-identical across arms.
- **Plain-English terms:** *Wilson interval* = honest range for one rate. *Newcombe interval* = honest
  range for the *difference* of two rates. *point estimate* = the single best-guess number (here the
  raw delta) before error bars. *straddles zero* = the difference interval includes 0, so you can't
  tell the two arms apart.

## D17 — S4 measured result: error-recovery closes the injected gap (a real result by the CI gate) ⭐
- **The result:** the live ablation on GLM-4.6 at **rate 0.6, N=40 distinct seeds** —
  **baseline 27/40 = 67.5%** (Wilson 95% CI [52.0%, 79.9%]) vs **+error-recovery 40/40 = 100%**
  (Wilson 95% CI [91.2%, 100%]). **Gap closed: +32.5%**, **Newcombe 95% CI [+17.3%, +48.0%]**. The
  error-recovery arm absorbed **104** transient 503s at the harness level, spending zero model turns.
- **Why we may call it a result (not over-claimed):** the Newcombe interval on the *difference* clears
  0, *and* the two arms' Wilson bars don't overlap (79.9% < 91.2%) — both honesty checks pass (D7/D16).
  100% is a boundary, so the *honest* read of the mechanism arm is its Wilson lower bound (91.2%), not
  "certainly perfect"; that's exactly what the interval is for.
- **The mechanism story, confirmed:** baseline's 13 misses were **all** `max_steps` — the bare loop's
  only recovery is the *model* re-calling a 503'd tool, which burns its 6-turn budget (retry-
  exhaustion). Error-recovery retries at the *harness* level (`max_recoveries=3`) without spending a
  turn, so all 13 are rescued. This validates D14's bet: error-recovery — not retry-nudge — is the
  guardrail that moves *this* number.
- **Honesty caveat (load-bearing):** the gap is **injected** (a controlled fault-recovery testbed, the
  rate a published knob). This measures recovery of a clean transient-fault *subset* of failures; the
  **natural-gap stretch** (D12) — eliciting GLM's *own* mechanical failures on a harder task and
  re-running the same guardrail — remains future work and would show how much of GLM's real failure
  surface error-recovery covers.
- **Reproduce:** `uv run ablation.py z-ai/glm-4.6 40 0.6` (writes `runs/ablation-summary.json`).

## D18 — S5 scope = draw the gap-closure chart (Option B); retry-nudge + natural-gap deferred ⭐ *(signed off 2026-06-28 — built; outcome in the **Built (S5)** note below)*
- **The choice:** make S5 the **gap-closure chart** — turn the two arms already measured in S4
  (baseline 67.5% vs +error-recovery 100%, D17) into the project's headline figure, with the
  confidence intervals drawn as error bars. **No new GLM runs** — the numbers come straight from the
  saved S4 result.
- **Options weighed:** (a) draw the chart now from the data in hand ✅ · (b) build **retry-nudge** as
  a second mechanism arm first · (c) chase the **natural gap** (drop injected faults; harden the task
  until GLM fails on its own merits, D12).
- **Why the chart first:** it's the literal deliverable, the data is already measured *and saved*, and
  our own methodology rule is *build the ugliest end-to-end version first, then layer mechanisms one at
  a time* (D6). Drawing the figure now is low-regret, forces an honesty check on how the result reads,
  and tells us whether a third arm even earns its scope.
- **Why retry-nudge was *not* chosen first (load-bearing heads-up):** against our current fault type
  (transient **503**s) retry-nudge would most likely measure **~null** — the bare loop already
  re-calls a 503'd tool on its own, and error-recovery already absorbs those faults (D14/D17). It only
  shows a real lift against a failure it *actually* fixes (e.g. a **malformed tool call**), which would
  mean adding a *new fault type* to `faults.py` first. So "build retry-nudge" really means "add a
  malformed-call fault **and** the arm" — more scope, with a genuine risk of a null bar. Kept as a
  clean S6 sibling.
- **The chart design (sub-options — *signed off and built*):**
  - *Data source:* read the **saved S4 summary** `runs/ablation-summary.json` (it is on disk and
    matches D17 exactly), **vendored** into a tracked file `docs/figures/gap-closure-data.json` so the
    figure regenerates in-repo with **no paid re-run**. (Rejected: hand-typing the numbers as constants
    — transcription risk; reading *only* the gitignored `runs/` copy — not reproducible after a clean
    clone.)
  - *What the figure shows:* a **two-bar completion-rate chart** — "Baseline (no mechanism)" vs
    "+ Error-recovery" — y-axis 0–100%, each bar carrying its **Wilson 95% CI** as a whisker and a
    `k/N` + `%` data label, plus the **gap (+32.5%)** annotated with its **Newcombe 95% CI
    [+17.3, +48.0]**.
  - *Honesty caption (required by the honesty rule):* printed on the figure itself — `N=40 paired
    seeds · fault-rate 0.6 · temp 0.7 · GLM-4.6 · gap is INJECTED (controlled fault-recovery testbed) ·
    104 transient 503s absorbed`. The chart must never read like a *natural*-gap result.
  - *Tooling/output:* **matplotlib** (add to `pyproject.toml`; `uv` installs on first run) → a
    committed **PNG** at `docs/figures/gap-closure.png`, generated by a new `chart.py`, then embedded
    in `README.md`. Pure label/format helpers get an offline `test_chart.py`; the render itself is
    smoke-verified by running `chart.py`.
- **Built (S5):** shipped exactly as specced — `chart.py` reads the vendored
  `docs/figures/gap-closure-data.json` and writes the committed `docs/figures/gap-closure.png`,
  embedded in `README.md` §7; pure helpers covered offline by `test_chart.py` (all seven suites green).
  Regenerate with `uv run chart.py` — no API, no model call. **On the figure:** baseline 67.5% →
  +error-recovery 100%, gap **+32.5%**, Newcombe 95% CI [+17.3%, +48.0%] → clears 0 (a real result by
  the D7/D16 gate).
- **Plain-English terms:** *error bar / whisker* = the small vertical line on a bar showing its
  confidence interval (the honest range around the height). *vendoring* = committing a copy of an
  otherwise-uncommitted file into the repo so the build doesn't depend on something git-ignored.
  *DPI* = dots per inch, the resolution of a saved image.

---

## D19 — S6 = the retry-nudge arm on a NEW malformed-call fault → a measured NULL ⭐ *(scope + fault design signed off 2026-06-29; built + measured 2026-06-29 — outcome in the **Measured result** note below)*

This is a **start-of-stage brief** (written before the code, per the per-stage rhythm). It records
the scope we locked, the design fork inside it, and one load-bearing honesty risk to weigh before
spending on the live run.

- **The choice (signed off):** make S6 the project's **second guardrail arm — retry-nudge** —
  measured on a **new fault type it can actually fix**. Error-recovery (S4) was the guardrail for
  *transient* faults; retry-nudge is the guardrail for *malformed* ones.
- **Scope options weighed:** (a) build the retry-nudge arm (needs a new malformed-call fault) ✅ ·
  (b) chase the **natural gap** (drop injected faults, harden the task until GLM fails on its own —
  D12's headline prize, but open-ended/high-variance) · (c) freeze scope and write up (the S5 chart
  is already the deliverable — lowest effort, thinnest learning).
- **Why (a):** it's the methodology's own rule — *layer one mechanism at a time* (D6) — it's bounded
  and reuses every seam, and it gives the project a **second measured bar** (the whole point is
  measuring how much *each* guardrail closes the gap). It also upgrades the testbed so the
  natural-gap stretch (b) later stands on richer ground. Chosen over (b) because (b) is higher-variance
  and better attempted once two clean injected-gap measurements exist; over (c) because the deliverable
  is a *measurement project*, and one bar is a thin story.

### Why retry-nudge needs a NEW fault (the load-bearing reason it wasn't trivially next)
Against our existing **transient 503** fault, retry-nudge measures **~null**: the bare loop already
re-calls a 503'd tool on its own, and a transient fault clears on *any* fresh re-call (D14/D18). A
guardrail only earns a real bar against a failure it *actually* fixes. Retry-nudge's matched failure
is a **malformed call** — the model's *own* call is wrong, so a blind harness re-call can't fix it,
but re-prompting the *model* to correct it can. So "build retry-nudge" necessarily means "build a
malformed-call fault first."

### The fault design (signed off): reject-and-hint
- **Options weighed:** (1) **reject-and-hint** ✅ · (2) route-around a hard-down tool (broader
  "adapt your plan" recovery, but adds a fallback tool + a looser story) · (3) use GLM's *own*
  malformed calls, no injection (most honest but unreliable to trigger — effectively the natural-gap
  path for this fault class).
- **The mechanism:** at a seeded rate an "armed" lookup tool **rejects the documented parameter**
  (`order_id` / `zone`) with an informative `400 invalid_argument: … use 'id' / 'region' instead`
  error; a **corrected** call (`id=` / `region=`) bypasses the fault and returns the real record.
  Disclosed as injected, exactly like the 503.
- **Two load-bearing properties the design must have:**
  1. **Classified *permanent*, not transient.** The `400 invalid_argument` string matches none of
     `agent._is_retryable`'s hints, so **error-recovery leaves it alone** — its harness-retry only
     fires on *transient* errors (D17). That separation is exactly what we want, and it's *free*
     (already built).
  2. **Sticky to an identical re-call.** The 503 is a fresh coin-flip *per call*, so any re-call
     clears it. A malformed fault must instead be deterministic on the call itself (armed per
     `seed`+tool, not re-drawn), so a **blind resend keeps failing and only a *corrected* call
     succeeds.** Without stickiness a lucky resend would pass and we'd be measuring luck, not
     correction.

### The experiment (proposed): 3 arms on ONE testbed
Run **baseline / +error-recovery / +retry-nudge** all on the **malformed-fault** testbed — same
faults, one completion-rate axis, three bars:
- **baseline** — no mechanism (the control).
- **+error-recovery** — expected **≈ baseline** (a permanent fault isn't retried). This arm is the
  *in-experiment control* that *shows* the wrong guardrail doesn't help — guardrail **specificity**.
- **+retry-nudge** — expected to **lift** (the model corrects its call when re-prompted).

This is a cleaner design than a 2×2 (transient×malformed): holding the fault fixed and varying only
the guardrail makes the contrast a single, legible ablation. Measured with the **same** Wilson +
Newcombe CIs and the straddles-zero honesty gate (D16). Each non-baseline arm gets a Newcombe
interval **vs the shared baseline**.

### The retry-nudge mechanism
A new `nudge` toggle on `agent.run` (sibling to S4's `recover`). When a non-terminal tool call fails
(after any recovery), the harness appends **one explicit corrective re-prompt** that turn —
"that call failed: …; don't repeat it, fix the arguments per the error, and call again" — and counts
a `nudge`. Unlike error-recovery (retries at the *harness*, **no** model turn), retry-nudge spends a
**model turn** (the re-prompt), which is the defining cost contrast (D14). The bare baseline appends
nothing (it just feeds the raw error back as the tool result and loops).

### The honesty risk to weigh BEFORE the paid run (load-bearing)
GLM-4.6 may **self-correct from the hint in the baseline already** (it sees the `use 'id'` error as a
tool result and fixes its next call without any nudge). If so, retry-nudge measures **null** and the
chart is flat. We handle this honestly, not by tuning for a win:
- A cheap **live pilot** (~N=6, all 3 arms) runs *first*, to confirm the wiring and check the baseline
  isn't already at ceiling. If it is, we retune the *difficulty* honestly (raise the rate, arm both
  tools, trim the step budget) and **say so** — never weaken the baseline's information to manufacture
  a gap.
- Either outcome is a real finding under the CI gate: a lift ("retry-nudge recovers malformed calls")
  or a null ("GLM self-corrects malformed calls unaided; the explicit nudge adds nothing at this N").
- The **robust** part of the result holds regardless: **error-recovery ≈ baseline** on malformed calls
  is structural (a permanent error isn't retried), so S6 demonstrates **guardrail specificity** even in
  the worst case.

### Measured result (S6): a clean NULL — GLM-4.6 self-heals malformed calls ⭐
The pilot fired the predicted risk and the N=20 confirmation pinned it (seeds 0–19, rate 0.6):
- **baseline 20/20 = 100%** · **+error-recovery 20/20 = 100%** · **+retry-nudge 20/20 = 100%** — and the
  nudge arm *did* issue **26** corrective re-prompts, so the faults armed and the mechanism worked; it
  just had no work to do.
- Both gaps vs baseline: **+0.0%**, Newcombe 95% CI **[−16.1%, +16.1%]** → straddles 0 → a **null** by the
  D16 gate. Reported as a null, not dressed up. All three Wilson intervals are [83.9%, 100%].
- **Mechanism (verified in the trajectories):** GLM reads the `400 … use 'id' instead` hint *as a tool
  result* and re-calls with the corrected parameter on its very next turn, unaided. So the explicit nudge
  is redundant, and error-recovery is structurally inert (a permanent error is never retried).
- **Why no honest tuning rescues it:** the nudge changes neither the *information* (the hint is already in
  the tool result) nor the *turn economics* (self-correcting and nudge-then-correcting each cost one extra
  turn), so raising the rate or trimming `max_steps` hurts both arms equally — they never separate. A win
  would require weakening the hint's information, which would be dishonest (and would only floor both arms).
- **The finding (the real deliverable):** a guardrail earns its keep only where the model *can't help
  itself*. S4's +32.5% was specifically **turn-exhaustion** recovery — transient faults made GLM retry
  until it ran out of steps, and a no-turn harness retry rescued it. Malformed calls don't exhaust turns
  (GLM fixes them in one extra step), so neither guardrail moves the number. The "each guardrail fixes its
  own failure" intuition has a boundary: the model's own competence. The figure
  (`docs/figures/malformed-gap.png`, title auto-set from the verdict to *"On malformed faults, no guardrail
  beats the baseline"*) and README §8 state this plainly.
- **Process win (cheap de-risk):** the ~18-trial pilot caught the null *before* the full run — we spent ~60
  trials total, not a wasted N=40×3, and still produced a rigorous, defensible negative result. The
  apparatus (malformed fault + retry-nudge arm + N-arm harness + N-bar chart) is reusable for future
  models/faults.
- **Reproduce:** `uv run malformed_ablation.py z-ai/glm-4.6 20 0.6` (writes `runs/malformed-ablation-summary.json`).

### Plain-English terms
- *malformed call* = the model's tool call is itself wrong (wrong parameter name/type, bad JSON), so
  the tool rejects it — as opposed to a *transient* fault where the call is fine but the service
  hiccups.
- *retry-nudge* = a guardrail that **re-prompts the model** to fix and retry a failed call; costs a
  model turn. Contrast *error-recovery*, which retries at the **harness** and costs **no** turn.
- *sticky fault* = a fault that recurs on an *identical* re-call (so only a genuinely *changed* call
  clears it), as opposed to a fresh per-call coin-flip.
- *guardrail specificity* = each guardrail fixes its own failure type and not others (error-recovery↔
  transient, retry-nudge↔malformed) — the thing the 3-bar chart is built to show.
- *pilot* = a tiny, cheap trial run done first to de-risk a bigger, costlier one.

---

## D20 — S7 = the natural-gap hunt (Option B), de-risked by a pilot; harden via longer-chain + bigger-record-set ⭐ *(scope + lever + pilot design signed off 2026-06-29; pilot result in the **Measured result** note below)*

This is a **start-of-stage brief** (written before the code, per the per-stage rhythm). It records the
scope we locked, the lever chosen to harden the task, the load-bearing insight that reshapes how the hunt
must run, and the pre-committed routing rule so the pilot result is honest either way.

- **The choice (signed off):** make S7 the **natural-gap hunt** (DECISIONS D12's headline prize): drop the
  injected faults and **harden the task itself** until GLM-4.6 fails on its *own* mechanical merits, then
  re-run the existing guardrails to see if they close that *natural* gap. De-risked by a cheap **pilot
  first** — the same move that paid off in S6.
- **Scope options weighed:** (A) **declare done** — treat the S5 chart (+32.5% real) + the S6 null as the
  finished, honest deliverable · (B) **hunt the natural gap, pilot-gated** ✅ · (C) **hunt + pre-commit to a
  third guardrail** (a validation/self-check step) if the natural failure is a type the current guardrails
  can't catch.
- **Why (B):** it's the project's own rule — *prove a gap exists before building any guardrail to recover
  from it* (D6) — and the binding constraint here is the **statistics (noise floor), not the code**, so the
  highest-value next dollar is a small spend to learn whether a natural gap even exists. B keeps a pre-agreed
  honest off-ramp: if the pilot finds nothing we fall back to A *with evidence* ("even a hardened task
  doesn't break GLM"), not a shrug. C is the same bet with more chips down — deferred until the pilot shows
  the gap's *type* actually warrants a new guardrail (we don't build C blind).

### The load-bearing insight (this reshapes how B must run)
Our two guardrails only ever fire on a **tool-call error**: error-recovery retries a *transient* error
(503/timeout — no model turn); retry-nudge re-prompts the model to fix a *malformed* call (one model turn).
But a genuinely hard task most often breaks a *third* way — GLM threads the wrong field, picks the wrong
record, or fumbles the total and **submits a wrong number with no error at all**. Mapping each natural
failure type to what (if anything) we own that can close it:

| Natural failure type | Guardrail that can close it |
| --- | --- |
| Transient tool error (503/timeout) | error-recovery — but a *natural* task has no flaky service; only appears under injection |
| Malformed / wrong-param call | retry-nudge — but **S6 showed GLM self-heals these in one turn → null** (D19) |
| **Wrong answer, no error** (wrong field/record/total) | **none — needs a *validation* guardrail = Option C** |
| Never submits / runs out of steps | retry-nudge *might* refocus a flailing run; otherwise none |

So the honest expectation: hardening a strong model most often lands in **row 3 — a "validation gap" that
pure-B cannot close.** That isn't a reason to skip B; it's the reason the pilot exists — to tell us *which
row we're in* before spending on a full N≥20 experiment.

### The lever (signed off): longer chain + bigger, confusable record set
- **Options weighed:** (1) **longer chain** — 3–4 *chained* lookups (add order→customer→discount; total =
  items + shipping − discount) ✅ · (2) **bigger / confusable records** — ~15 orders with look-alike ids,
  asked *by description* not exact id, so the model must disambiguate ✅ · (3) **trickier arithmetic** —
  **rejected: off-thesis**, it manufactures *cognitive* (can't-reason-it) failures, the wrong kind
  (scenario.py deliberately keeps the math trivial) · (4) **stricter tool params** — **rejected: ~re-runs
  S6** (GLM self-heals malformed calls → likely null).
- **Chosen: 1 + 2 together** as "hard task v1." Both produce *mechanical* failures (the on-thesis kind), and
  a longer chain through a confusable record set naturally yields a *mix* of unknown-id **errors** and
  wrong-**answers**, so the pilot's triage cleanly reveals which row above we land in. Stacking two levers is
  fine for a pilot — the goal is *detection, not attribution*; if it breaks we can pare back.
- **Built as a NEW scenario** (`scenario_hard.py`), leaving the frozen `ORDER_SCENARIO` (and the shipped S5
  figure + its tests) untouched. `MAX_STEPS` scales up with the chain length so a "miss" means *got it
  wrong*, never *ran out of room* (a budget artifact ≠ a natural failure).

### The pilot (the de-risk Kyle approved)
- **Bare baseline only** (`recover=False, nudge=False`), **clean** (no fault injection), **N=8**, GLM-4.6,
  temp 0.7. The gating question is just *"does a gap exist, and of what type?"* — guardrail arms are
  premature until we know the type. ~a few cents, ~2–3 min.
- **Hand-read every miss** and classify it by the table above (failure triage).
- **Pre-committed routing rule (so the result is honest either way):**
  - GLM still ~aces it (no gap) → **A (declare done)** with evidence; optionally one stronger lever first.
  - Gap, **tool-error** type → **full B**: re-run the existing guardrails, measure with Wilson/Newcombe + a chart.
  - Gap, **wrong-answer** type → **stop and bring Kyle the A-vs-C decision** (pure-B would null; closing it
    needs a validation guardrail = C). Never build C silently.

### Measured result (S7 pilot): hardened task v1 — GLM-4.6 aces it 8/8, NO natural gap
The cheap de-risk did its job and gave a clean signal. On the bare baseline, clean (no injected faults),
**GLM-4.6 scored 8/8 = 100%** on "hard task v1" (N=8, temp 0.7, max_steps=12). Every run **submitted 82**
(the exact ground truth) — so GLM disambiguated the right Globex/EAST order out of 15 look-alike records,
threaded the 4-lookup chain, and computed `90 + 12 − 20` correctly every time. **Zero misses** to triage —
no natural gap surfaced at this difficulty.
- This is the **third** independent signal that GLM-4.6 is robust at multi-step mechanical tool use: 20/20
  on the clean S2 task (S3), self-heals malformed calls (S6), and now 8/8 on a longer, confusable task (S7).
- **Routing (per the rule above):** no gap → **A (declare done)** *or* **escalate the lever once** (a harder
  pilot). Brought to Kyle, who chose to **escalate once** (hard task v2) — resolved below. (Even a gap found
  by escalating would most likely be the row-3 *wrong-answer* type, which reopens the A-vs-C question
  rather than rescuing pure-B.)
- **Cost:** prompt 21,452 / completion 3,205 tokens, ~1 minute — a trivial spend for a decisive answer.
- **Reproduce:** `uv run pilot.py` (clean baseline, hardened task); `uv run test_scenario_hard.py` (offline).

### Escalation (hard task v2) + final resolution: declare done ⭐
Per the bounded-escalation rule, we pushed difficulty up once more — "hard task v2": a **5-lookup** chain
(added a per-zone tax → total = item + shipping + tax − discount) through **~25 records** with a
**near-duplicate-customer** distractor ("Globex" vs "Globex Labs", each with its own EAST order). Clean
baseline, N=8.
- **Result: 8/8 = 100% again** — every run submitted the exact ground truth (117). GLM disambiguated the
  right customer *and* order, threaded all five lookups, and computed `120 + 12 + 5 − 20` every time.
- **Resolution (the stop rule fires): declare done (route A).** ≥7/8 was the pre-agreed stop, so we stop —
  no endless chase. S7's deliverable is this **negative result**, stated plainly.
- **The finding:** across four independent probes — 20/20 clean (S3), self-heals malformed (S6), 8/8 hard-v1,
  8/8 hard-v2 (S7) — **GLM-4.6 shows no measurable *natural* gap at reasonable mechanical difficulty.** To
  study reliability guardrails on this model you must *inject* faults — exactly what S3–S6 did, and disclosed.
  The injected fault-recovery testbed (+32.5% real for error-recovery, an honest null for retry-nudge) stands
  as the project's legitimate, honest deliverable.
- **Why we didn't push further (honesty):** cranking difficulty until a strong model finally slips tends to
  manufacture either *cognitive* failures (off-thesis — the model can't reason it) or *wrong-answer-no-error*
  (validation) failures the existing guardrails can't close anyway (row 3 above). Neither rescues pure-B, so
  more escalation would spend money to *weaken*, not strengthen, the honest story.
- **Reproduce:** `uv run pilot.py v2` (clean baseline, hard task v2); both pilots are offline-guarded by
  `uv run test_scenario_hard.py`.

### Plain-English terms
- *natural gap* = GLM failing on a **clean** task (no injected faults) just because the task is genuinely
  hard — as opposed to the *injected* gaps of S3–S6.
- *validation guardrail* = a check that the model's **answer** is right (or self-consistent) before
  accepting it — catches *wrong-answer-no-error* failures that error-recovery and retry-nudge (which only
  see tool errors) structurally cannot.
- *failure triage* = hand-reading a run's step-by-step trajectory to classify *why* it failed, not just
  that it did.
- *on-thesis failure* = a **mechanical** breakdown of a step (wrong field threaded, wrong record, skipped
  link) — the failure class this project measures — versus a *cognitive* one (the model can't reason the
  task), which the task design deliberately avoids.

## D21 — S8 = weak-model natural-gap experiment → pivoted to a NEW *submit-nudge* guardrail on mistral-nemo ⭐ *(scope signed off 2026-06-30; two pilot-gated forks resolved live; measured result appended below after the run)*

This is a **start-of-stage brief** (per the per-stage rhythm), but S8's brief **evolved through two pilot-gated
forks** — the rhythm working as intended: a cheap pilot before each commit kept us honest as the model
surprised us. It records what we locked, what the pilots found, and why S8 became a *new guardrail* stage.

### The original choice (signed off 2026-06-30)
S7 proved GLM-4.6 has **no natural gap**. S8's move: hold the task fixed and **swap in a weaker model**, then
run the existing arms on the **clean** task — the variable we flip is the *model's capability*, so the claim is
the **capability × guardrail interaction**, not "GLM needs guardrails."
- **Scope options weighed:** (A) **MVP** — one weak model, pilot-gated 3-arm clean ablation + the N-bar chart
  ✅ · (B) **capability ladder** — 2–3 models → a "lift-vs-capability" curve (richer, ~2–3× cost; deferred).
- **Model (signed off):** scouted OpenRouter (254/338 models are tool-capable; the *tiny* 1–3B models don't
  even expose tool-calling, so the degenerate-0% floor partly self-avoids). Picked
  **`meta-llama/llama-3.1-8b-instruct`** first — canonical, cheap ($0.02/0.03 /Mtok), the most defensible
  "weak vs GLM" story — with a fit-pilot rule to ladder up/down.

### What the pilots found (the load-bearing pivot)
The fit pilots (N=8, clean) did **not** land in the pre-registered "malformed tool call" sweet spot — they
revealed a **capability cliff** with two *different* non-tool-error failure modes, both scoring **0/16** and
both **invisible to the existing arms**:

| Model | Computes 158? | Submits? | Natural failure (→ maps to D20's table) |
| --- | --- | --- | --- |
| Llama-3.1-8B | ❌ hallucinates (even submits formula strings) | yes — garbage (`1234.56`, `10.0`) | **validation gap** — wrong answer, no error (D20 **row 3**) |
| mistral-nemo (12B) | ✅ yes (`158`) | ❌ narrates "calling submit_answer…" then stops | **protocol gap** — right answer, never calls the tool (D20 **row 4**) |

Neither is a *transient* fault (error-recovery's target) or a *failed/malformed* call (retry-nudge's target),
so a 3-arm run on either would be an **uninteresting triple-null**. Per the pre-agreed rule, the second
bifurcation → stop and re-point.

### The pivot (signed off 2026-06-30): build a *submit-nudge* guardrail, ablate mistral-nemo
mistral-nemo's failure is the **most recoverable one possible** — the model is *right*; it just doesn't pull
the terminal trigger. This is exactly **D20's row 4** ("never submits → *might* refocus, otherwise none"), now
given its targeted guardrail.
- **The mechanism (new):** **submit-nudge** — when a turn ends in prose with **no submission yet**, re-prompt
  *"you haven't called submit_answer; do it now"* and continue (instead of ending as `no_submit`). A model
  turn, like retry-nudge — but fired on a *missing terminal call*, not a *failed* one.
- **The experiment — guardrail specificity** (a clean 3-arm ablation on mistral-nemo):

  | Arm | Expectation | Why |
  | --- | --- | --- |
  | baseline | ~0–12% | knows `158`, won't submit |
  | +retry-nudge | ≈ baseline (**null**) | only fires on a *failed* call; a no-submit isn't one |
  | **+submit-nudge** | **real lift** | re-prompt → emits the call it already intended |

  The point isn't just a bar — it's the project's through-line: **a guardrail helps only where it matches the
  failure** (S4 recovery fixed turn-exhaustion; S6 nudge nulled on self-healing; S8 submit-nudge fixes
  no-submit while retry-nudge nulls *in the same run*).
- **Options weighed at the pivot:** (1) **submit-nudge on mistral-nemo** ✅ · (2) **validation guardrail on
  Llama-8B** — the parked idea (recompute from fields, reject mismatches); bigger build, noisier testbed →
  **parked to ROADMAP as a separate research task** · (3) **keep laddering models** — rejected; two
  bifurcations make a naturally-malformed-call model look rare.
- **Honesty caveat (goes in the chart caption):** part of mistral-nemo's no-submit is it *asking* "shall I
  submit?", and our one-shot harness ends on prose — so the submit-nudge is partly the harness replying "yes,
  go." A real failure and a real guardrail, stated plainly; and the gap is **natural** (no injection), unlike
  S3–S6.

### The pilot (the de-risk)
- **submit-nudge arm on mistral-nemo, N=8, clean.** Gate: does it lift completion materially over baseline
  (and does retry-nudge stay ~null)? Hand-read to confirm the lift is genuine `158` submissions, not
  artifacts. ~pennies. Only on a clean lift do we spend the full N≥20.

### Plain-English terms
- *submit-nudge* = a guardrail that re-prompts the model to call the **terminal** tool when a run ends without
  submitting (vs *retry-nudge*, which re-prompts after a **failed** tool call).
- *protocol gap* = the model has the right answer but fails the **interaction protocol** — here, never
  emitting the `submit_answer` tool call (narrating it as prose instead).
- *guardrail specificity* = a guardrail closes a gap **only when it matches the failure mode**; the wrong
  guardrail nulls (the in-experiment control).
- *bifurcation / capability cliff* = a task where models either **ace it** (too strong → no gap) or **fail
  wholesale** (too weak → 0%), with a narrow/empty "fails a *little*, mechanically" band between.

### Measured result (S8): submit-nudge closes the natural no-submit gap (+75 pp, REAL) ⭐
The pilot's signal held at scale. On the **clean** task (no injection), **mistral-nemo**, **N=20**, temp 0.7:

| Arm | Completion | Wilson 95% CI | Gap vs baseline (Newcombe 95% CI) | Verdict |
| --- | --- | --- | --- | --- |
| baseline | 0/20 = 0.0% | [0.0%, 16.1%] | — | 17 stalled (no-submit), 3 wrong (`140`) |
| +retry-nudge | 0/20 = 0.0% | [0.0%, 16.1%] | +0.0 pp [−16.1, +16.1] | **NULL** — fired **0** nudges (a no-submit is not a *failed* call) |
| **+submit-nudge** | **15/20 = 75.0%** | **[53.1%, 88.8%]** | **+75.0 pp [+47.8, +88.8]** | **REAL — clears 0** (fired **15** submit-nudges) |

- **A real result by every gate:** the Newcombe interval clears 0, *and* the two Wilson bars don't overlap
  (baseline ≤16.1% vs submit-nudge ≥53.1%). Figure: `docs/figures/weak-gap.png` (README §9).
- **Guardrail specificity, in one experiment:** the *wrong* guardrail (retry-nudge) does literally nothing —
  it never fires, because the failure isn't a *failed* call but a *missing* one. Only the *matched* guardrail
  (submit-nudge) lifts. Same lesson as S4 (recovery↔turn-exhaustion) and S6 (nudge↔malformed, a null) — now on
  a **natural** gap.
- **The honest residual:** submit-nudge converted **all 17 stalls** into submissions (0 no-submit left), but
  5/20 of those were the model's `140` under-compute (item total, shipping forgotten) — a **validation** miss
  submit-nudge structurally can't fix. So the natural gap has two layers: a *protocol* gap (no-submit) that
  submit-nudge closes, and a residual *validation* gap that motivates the parked next experiment (ROADMAP
  "Parked").
- **The framing (honesty):** the gap is **natural** (the weak model's own failure on a clean task — no
  injection), unlike S3–S6's injected gaps. The caveat, stated on the figure: part of the no-submit is
  mistral-nemo *asking* "shall I submit?", and our one-shot harness ends on prose — so submit-nudge is partly
  the harness replying "yes." A real failure and a real guardrail. The claim is the **capability × guardrail
  interaction**: a weak-but-tool-capable model needs a guardrail GLM-4.6 (S6/S7) did not.
- **Infra note:** mistral-nemo's OpenRouter route rate-limits (429); we let the SDK ride it out
  (`max_retries=8` in `glm.py`) so a blip doesn't abort an arm — HTTP hygiene, not a measured mechanism.
- **Reproduce:** `uv run weak_ablation.py mistralai/mistral-nemo 20` (live); `uv run test_submit_nudge.py` +
  `uv run test_chart.py` (offline). All **eleven** offline suites green.

## D22 — S9 = the validation guardrail (Option A): recompute-from-retrieved-evidence, ablated on mistral-nemo *stacked on* submit-nudge ⭐ *(scope signed off 2026-06-30; this is the start-of-stage brief — awaiting design sign-off before any code)*

This is a **start-of-stage brief** (written before the code, per the per-stage rhythm). It records the
scope we locked, the guardrail's design, the one load-bearing honesty question ("how do you validate
*without* the answer key?"), the testbed pick and the evidence behind it, and the pilot that de-risks the
paid run. **The `⭐` marks a load-bearing entry.** Nothing here is built yet.

### The choice (scope signed off 2026-06-30)
Make S9 the project's **fourth guardrail — validation** (a *self-consistency* check on the model's final
answer), closing the **last uncovered failure row**: *wrong answer, no tool error* (D20 row 3 · the D21
residual · the ROADMAP "Parked" note). This completes the thesis — every failure class now has its matched
guardrail:

| Failure type | Matched guardrail | Prior result |
| --- | --- | --- |
| Transient tool error (503) | error-recovery (S4) | +32.5 pp ✓ (injected) |
| Malformed call | retry-nudge (S6) | null — GLM self-heals |
| Never submits (right answer, no terminal call) | submit-nudge (S8) | +75 pp ✓ (natural) |
| **Wrong answer, no error** (retrieved data, computed wrong) | **validation (S9)** | **← this stage** |

- **Scope options weighed:** (A) **build the validation guardrail** ✅ · (B) **capability ladder** — run S8's
  submit-nudge harness across 2–3 models for a lift-vs-capability curve (mechanical, reuses everything, but
  no new mechanism/insight and more live-call spend) · (C) **declare done & write up** — treat S4/S6/S7/S8 as
  the finished deliverable (lowest effort; leaves the last row uncovered).
- **Why (A):** it closes the exact row the project keeps pointing at, so it *completes* the "each failure →
  its matched guardrail" story rather than adding breadth. It's the most novel and the most defensible under
  scrutiny — the "validate without the answer key" design (below) is precisely the methodological care that
  reads as real engineering maturity. It stays fully on-thesis (mechanical failure, deterministic guardrail,
  Wilson/Newcombe CIs) and reuses the whole harness. Chosen over (B) (thinner — "more of the same") and (C)
  (stops one guardrail short of the capstone, and this one is within reach on the existing testbed).

### The failure it targets — and the evidence it's real *and* clean (a trajectory read, not a guess)
S8 left a residual: with submit-nudge on, mistral-nemo submitted the wrong `140` in **5/20** runs (item total
with **shipping silently forgotten**). Before choosing a testbed we **hand-read all 20 submit-nudge
trajectories** (`runs/submit_nudge/trial-*.jsonl` from the S8 run). Every one of the 5 wrong runs (trials 06,
09, 13, 16, 17) had **retrieved *both* inputs correctly** — `get_order` → `item_total_usd=140` **and**
`get_ship_rate` → `rate_usd=18` — then submitted `140` anyway. Zero wrong-record contamination; **100% pure
arithmetic/aggregation slip on correctly-retrieved evidence.** That is the textbook validation target: a check
that recomputes `140 + 18 = 158` from *the model's own retrieved data* catches all 5 — no answer key needed.

### The mechanism (new): `validate` — recompute from the model's own evidence, re-prompt on a mismatch
A fourth toggle on `agent.run()` (sibling to `recover` / `nudge` / `submit_nudge`). When the model calls the
terminal tool `submit_answer(value)`, **before accepting it as final**:
1. Reconstruct the **evidence** — the tool results the model actually received this run (the parsed
   `get_order` / `get_ship_rate` JSON it observed).
2. **Recompute** the expected total from that evidence, using the scenario's declared aggregation rule (sum
   the retrieved line items). This lives in the **scenario** (a new `Scenario.validate` callable), so the
   guardrail stays task-agnostic — it just calls `scenario.validate(submitted, observations)`.
3. If `value` **matches** the recomputed total → accept and stop (a normal submit).
4. If it **doesn't match** → *don't* accept: append one corrective re-prompt naming the retrieved components
   ("your total 140 doesn't match the data you retrieved: item total 140 and shipping 18 must both be included —
   recompute and resubmit"), count a `validation` nudge, and continue the loop (up to `max_steps`). Like
   retry-nudge / submit-nudge it spends a **model turn**; unlike them it fires on a *submitted-but-inconsistent*
   answer, not a *failed* or *missing* call.

### The honesty crux (load-bearing ⭐): self-consistency, NOT an answer key
The obvious objection: *"the oracle knows the answer is 158 by computing `item_total + rate`; if the validator
computes the same thing, haven't you just put the oracle inside the agent and forced 100%?"* The answer is no,
and the distinction is the whole integrity of the stage — it's the **input** each one reads:
- The **oracle** (`oracle.py`) computes from the **canonical records** (`ORDERS[TARGET_ORDER]`, `SHIP_RATES`),
  keyed by the *true* target order. It is authoritative and independent of the model; it can **never** be fooled.
- The **validator** computes from the **model's own retrieved observations** — whatever the model actually
  pulled back this run. It is only as good as the model's retrieval, and it **can** be fooled: feed it a
  *wrong-record* retrieval and it recomputes a self-consistent *wrong* total and accepts it (the oracle still
  fails it). So the validator does **not** trivially force an oracle-pass.
- Therefore it is a **self-consistency check** ("is your submitted number consistent with the evidence *you*
  gathered?"), a real deployable verifier pattern — not an answer key. The lift it measures = the fraction of
  wrong answers that were internal-consistency violations (right evidence, wrong arithmetic). Its structural
  **blind spot** (wrong-retrieval → self-consistent wrong answer) is disclosed, not hidden.
- **Two bright lines the code must honor:** (1) the validator **never reads `scenario.ground_truth`** — only
  the run's tool observations; (2) encoding the *aggregation rule* (sum the retrieved items) is the same
  narrow task/protocol knowledge every guardrail carries (error-recovery "knows" to retry transient; submit-nudge
  "knows" to call the terminal tool) — it is **not** the answer. On this nemo testbed retrieval is always
  correct, so the blind spot doesn't bite — but we state it plainly regardless.

### The testbed (signed off): mistral-nemo, *stacked on* submit-nudge
- **Options weighed:** (1) **mistral-nemo stacked on submit-nudge** ✅ · (2) **Llama-3.1-8B** (the parked
  target) — **rejected for now**: bigger headroom (~100% baseline fail) but a *messier* failure mix
  (hallucinated numbers, literal formula-strings, likely some bad retrieval), so much of its gap may be
  **un-validatable**; it needs a fresh fit-pilot to even characterize. Kept as a future harder testbed.
- **Why (1):** the trajectory read proved nemo's failures are the *cleanest possible* validator target
  (retrieved both inputs, forgot to add → 5/5 catchable from evidence, zero wrong-record noise), it **continues
  S8's exact testbed**, and it tells a clean **two-layer** story in one picture: submit-nudge gets the model to
  *submit*, validation gets it to submit *correctly*.
- **Why "stacked":** nemo's bare baseline is **0/20** (it never submits), so validation *alone* would have
  nothing to validate — the validation gap is *masked* by the no-submit gap until submit-nudge lifts it. So the
  honest controlled comparison **holds submit-nudge fixed and toggles validation**.

### The experiment: a 2-arm *stacked* ablation, **N=40**
| Arm | Config | Expectation | Role |
| --- | --- | --- | --- |
| `submit_nudge` (reference) | `submit_nudge=True` | ~75% | the layer below — the "baseline" for *this* ablation |
| `submit_nudge+validation` | `submit_nudge=True, validate=True` | ~95–100% | the matched guardrail; expected to lift |

- Same **Wilson** per arm + **Newcombe** gap (mechanism vs the submit-nudge reference) + the **straddles-zero**
  honesty gate (D16). Reuses `run_arms`; a new `validation_ablation.py` sets the reference arm to
  submit-nudge. For the figure, the bare **0%** baseline is shown as a context bar so the honest **full ladder**
  reads `0% → 75% → ~100%`.
- **Why N=40, not 20** (computed with `stats.py`, assuming validation catches the slips): the residual is a
  *smaller* effect than S8's headline (75% base, only 25% headroom), so N=20 is **knife-edge** — catch-all-5
  clears zero by a hair (75%→100%, Newcombe **[+3.8%, +46.9%]**) but catch-4-of-5 goes **null** (75%→95%,
  **[−3.2%, +42.3%]**). **N=40 is robust** — it clears zero even at catch-4-of-5 (75%→95%, **[+4.2%, +35.6%]**;
  catch-all-5 → **[+11.1%, +40.2%]**). nemo is cheap, so N=40 × 2 arms is still pennies.

### The honesty risk to weigh BEFORE the paid run (load-bearing)
- **It may null** if the weak model, once re-prompted, just *resubmits 140* instead of correcting. That's the
  same null-risk shape as S6, and either outcome is a real finding under the CI gate ("validation recovers the
  arithmetic-slip gap" **or** "even told it's inconsistent, this model won't fix it at N"). The **pilot** below
  checks exactly this before we spend.
- **Re-prompt verbosity is a sub-knob** (a "how loud is the hint" dial, to pin at pilot time): the re-prompt
  **names the retrieved components (140 and 18) and the rule (both must be included), but does NOT state the sum
  158** — so the model still does the (trivial, by-design) addition itself and the guardrail is a *consistency
  checker*, not a *solver*. If the pilot shows that terse form doesn't lift, we may state the recomputed total —
  and **disclose** that we did (it shifts the reading toward "the harness supplied the answer").
- **The "is it cheating?" question is answered above** (self-consistency, never `ground_truth`); the code
  review for S9 must verify the two bright lines hold.

### The pilot (the de-risk)
- **`submit_nudge=True, validate=True`, mistral-nemo, N=8, clean.** Gate: does validation **fire** on the `140`
  runs and **lift** completion over the ~75% submit-nudge base? **Hand-read** the caught runs to confirm they
  become genuine `158` resubmissions (not artifacts). ~pennies. Only on a clean lift do we spend the full N=40;
  if it's flat, we either dial the re-prompt louder (disclosed) or report the null.

### Plain-English terms
- *validation guardrail* = a check that the model's **answer** is right / self-consistent before the run
  accepts it — catches *wrong-answer-no-error* failures the tool-error guardrails (error-recovery, retry-nudge)
  and the protocol guardrail (submit-nudge) structurally cannot see.
- *self-consistency check* = "does your answer match the evidence **you** gathered?" — recomputed from the
  model's own tool results, **not** from the grader's ground truth (which would be an answer key).
- *stacked ablation* = an ablation whose "baseline" already has one guardrail on (here submit-nudge), so a
  *second* guardrail (validation) is measured on top — used when the lower guardrail is what makes the higher
  one's failure visible at all.
- *scaffolding* = a mechanism (submit-nudge) whose job here is to **expose** the failure another mechanism
  (validation) targets, by clearing the failure that was masking it.

### Measured result (S9): validation closes the residual wrong-answer gap (+25 pp, REAL) ⭐
The pilot's signal held at scale. On the **clean** task (no injection), **mistral-nemo**, **N=40**, temp 0.7,
the stacked ablation (both arms carry submit-nudge; validation is toggled on top):

| Arm | Completion | Wilson 95% CI | Gap vs submit-nudge (Newcombe 95% CI) | Verdict |
| --- | --- | --- | --- | --- |
| submit_nudge (reference) | 30/40 = 75.0% | [59.8%, 85.8%] | — | reproduces S8 exactly; 10 misses submit `140` |
| **+validation** | **40/40 = 100.0%** | **[91.2%, 100%]** | **+25.0 pp [+11.1, +40.2]** | **REAL — clears 0** (fired **5** validations) |

- **A real result by every gate:** the Newcombe interval clears 0 *and* the two Wilson bars don't overlap
  (submit-nudge ≤85.8% vs +validation ≥91.2%). Figure: `docs/figures/validation-gap.png` (README §10).
- **The mechanism verified in the trajectories (the pilot gate, done by hand):** validation fired on **6/6**
  of the `140` submissions it ever saw across the pilot + full run and converted **every one** to a genuine
  `158` resubmission — zero mismatches. A textbook trace (validation-arm trial-01): the model fetched the rate
  (`18`) and submitted `140` in the *same* turn; validation recomputed `140 + 18 = 158` from the just-threaded
  tool result, rejected `140`, and the model corrected to `158` on the next turn. The `evidence` it logged
  (`item_total_usd: 140, rate_usd: 18, expected: 158`) is recomputed from *retrieved data*, never `ground_truth`.
- **The completed thesis:** every failure class now has its matched guardrail, each measured under the same CI
  gate — transient→error-recovery (+32.5 pp, injected), malformed→retry-nudge (null, GLM self-heals),
  no-submit→submit-nudge (+75 pp, natural), **wrong-answer→validation (+25 pp, natural)**. And **guardrail
  specificity** holds a fourth time: on this same testbed retry-nudge (S8) and error-recovery are inert — only
  the guardrail *matched* to the failure moves the number.
- **The honesty crux, upheld in code (the load-bearing bright lines):** the validator reads only the run's tool
  observations and **never** `scenario.ground_truth` — it is a *self-consistency* check, not an answer key. It
  can be fooled by wrong-record retrieval (it would accept a self-consistent-but-wrong total); on this testbed
  retrieval is always correct, so the residual it closes is **pure arithmetic slip** (all `140`s had fetched both
  `140` and `18`). Stated on the figure. The re-prompt names the components (`140`, `18`) and the rule (add both)
  but **not** the sum `158`, so the model still does the trivial addition itself — a *checker*, not a *solver*.
- **The framing:** the gap is **natural** (the weak model's own failure on a clean task — no injection), and the
  full ladder on this model is now **0% → 75% → 100%** (bare → +submit-nudge → +validation). The claim remains the
  **capability × guardrail interaction**: a weak-but-tool-capable model needs guardrails GLM-4.6 (S6/S7) did not.
- **Process win (cheap de-risk, again):** the ~N=8 pilot confirmed the mechanism fired and lifted before the full
  spend; N=40 (not 20) was chosen up front because `stats.py` showed the ~25 pp residual is knife-edge at N=20
  (a null if validation catches 4-of-5) but robust at N=40 — the binding constraint is the statistics, not the code.
- **Reproduce:** `uv run validation_ablation.py mistralai/mistral-nemo 40` (live); `uv run test_validation.py` +
  `uv run test_chart.py` (offline). All **twelve** offline suites green.

---

## D23 — S10 = the harder validation testbed (Option A): the *same* validation guardrail on Llama-3.1-8B's hallucination gap, UN-stacked ⭐ *(scope signed off 2026-07-03; this is the start-of-stage brief — the fit-pilot gates the full spend)*

This is a **start-of-stage brief** (written before the code, per the per-stage rhythm). With the core thesis
complete after S9 (four failure classes, four matched guardrails, each measured under the CI gate), anything
from here is upside, not obligation — so the decision was *"what's the highest-value next measurement, or is
it time to write up?"*

### The choice (scope signed off 2026-07-03)
Make S10 the **harder validation testbed** parked at S9 (ROADMAP "Parked", 2026-06-30): re-run the S9
**validation** guardrail — unchanged — on **`meta-llama/llama-3.1-8b-instruct`**, whose natural failure on the
clean task is *messier* than nemo's clean arithmetic slip: it **hallucinates** the final number even with the
right data in hand (S8 fit-pilot: 0/8; submitted garbage like `1234.56`, `10.0`, and — twice — the literal
formula string `"item_total_usd + ship_rate"`).

- **Scope options weighed:** (A) **this** ✅ · (B) **capability ladder** — same guardrails across 2–3 models
  for a lift-vs-capability curve (strong summary figure, pure reuse, but no new mechanism and the most live
  spend; passed over once already at D22 as "more of the same") · (C) **true self-hosted endpoint**
  (llama.cpp/Ollama — the original *Forge* framing; biggest infra lift + risk, and partly duplicates S4's
  injected-transient result) · (D) **declare done + portfolio write-up** (fully legitimate — the thesis is
  complete — but forgoes the one cheap novel measurement still on the table; remains available *after* A).
- **Why (A):** it's the only path that produces a **genuinely new measurement** at low cost — it turns the
  validator's *disclosed blind spot* (D22's honesty crux) from a caveat into a **number**. On nemo the
  wrong-answer residual was 100% pure slip, so validation caught 6/6 — a best-case testbed. Llama's gap is a
  messy mix: some failures are slips on correctly-retrieved evidence (validation-catchable) and some are
  hallucination / missing-or-wrong retrieval (structurally **un-validatable** by a self-consistency check).
  Measuring how much of a *messy natural* wrong-answer gap validation closes — and how much it structurally
  can't — is the honest stress test of S9's result. Pilot-gated, so the downside is pennies.

### What's NEW vs S9 (the design deltas — everything else is reuse)
1. **UN-stacked ablation.** nemo never submitted, so S9 had to stack validation on submit-nudge to unmask the
   gap. **Llama submits on its own** (garbage, but it calls the terminal tool — D21's pilot table), so the
   S10 reference arm is the **bare baseline** and validation toggles directly:
   `VALIDATION_ONLY_ARM = {"label": "validation_only", "run_kwargs": {"validate": True}}` (no `submit_nudge`).
   A cleaner 2-arm design; nothing else in the harness changes.
2. **The decomposition metric (the novel part).** Hand-read every miss and split the gap into:
   **(i) validation-catchable** — retrieved both inputs, submitted an inconsistent number → the guardrail
   fires; **(ii) un-validatable** — never retrieved the evidence (validator *accepts by design*: it returns
   "can't recompute" rather than guess) or non-numeric submissions (validator passes them through; the oracle
   fails them). Slice (ii) is D22's blind spot, now **measured** instead of merely disclosed — the figure
   caption states both shares plainly.
3. **Zero mechanism code.** `agent.run(validate=True)` and `Scenario.validate` (`_validate_order_total`) are
   reused byte-for-byte — including its two accept-by-design rules (missing evidence → accept; non-numeric →
   accept, oracle fails it), which are exactly what makes slice (ii) measurable. New code is only the arm
   config, a thin `hallucination_ablation.py` runner (mirrors `validation_ablation.py`), and offline tests.

### Pre-registered pilot rules (decided BEFORE the pilot, ~pennies)
**Pilot: N=8 per arm (baseline / +validation), clean task, llama-3.1-8b, hand-read all trajectories.**
- **Fires + lifts** → size the full N with `stats.py` from the pilot rates (the same knife-edge analysis as
  D22 — the binding constraint is the statistics, not the code), then run the full ablation.
- **Llama mostly *doesn't* submit** (contradicting the S8 pilot) → the no-submit gap is masking again;
  consider a disclosed third arm (`submit_nudge + validate`) rather than pretending the 2-arm design fits.
- **Validation never fires** (all misses are missing-evidence or non-numeric) → that is a **blind-spot-
  dominant finding**: report the decomposition honestly; a null under the CI gate is still a real result.
- **Fires but doesn't lift** (model resubmits the same wrong number) → the S6-shaped null; report it.

### Honesty framing (unchanged from D22, restated for this testbed)
The gap is **natural** (clean task, no injection). The validator stays a *self-consistency check, never an
answer key* — the two bright lines (never reads `scenario.ground_truth`; re-prompt names components, not the
sum) must survive code review unchanged. Expected headline: *"on a messy natural wrong-answer gap, validation
recovered X pp; the remaining Y pp is un-validatable (bad/missing retrieval) — the blind spot, quantified."*
X may be small or null; either way it's the measurement.
