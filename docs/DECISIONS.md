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
- **Status:** decided, not yet built (arrives with the S4 runner).
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
