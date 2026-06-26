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
