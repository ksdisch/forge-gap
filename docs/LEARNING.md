# forge-gap — Learning Log

The plain-English story of how forge-gap is built, stage by stage, written so you can
*defend every line*. Each stage has: what we built, the teaching note (the one idea worth
keeping), the new vocabulary, and 3 recall questions — try them before you reveal the answer.

Quick map: [`ROADMAP.md`](ROADMAP.md). The *why* behind choices: [`DECISIONS.md`](DECISIONS.md).
A running **glossary** is at the bottom of this file.

---

## S0 — Foundation: a client + a smoke test

**What we built.** Two files:

- `glm.py` — a tiny wrapper that lets our Python code talk to the GLM-4.6 model. It points at
  *OpenRouter* (a service that resells many models behind one **OpenAI-compatible** API — meaning
  the same code shape works whether you're calling OpenAI or GLM). The one function you reuse
  everywhere is `chat(messages, ...)`, which passes extras like `tools` and `temperature`
  straight through to the API.
- `verify.py` — a **smoke test**: (1) a plain "say hi" chat and (2) one **tool-calling**
  round-trip (asking the model to use a `get_weather` tool). If both work, the setup is sound.

**Teaching note.** Tool-calling is the heart of every agent, so we prove it *on day one* instead
of discovering on day five that it never worked. Make the risky thing visible early.

**New words.** *API*, *OpenAI-compatible*, *OpenRouter*, *tool-calling*, *smoke test*.

**Recall — try before you reveal:**

Q1. Why prove tool-calling in S0 instead of later?

<details><summary>answer</summary>

Every later stage is an agent that depends on tool-calling. If it's broken, you want to know before building anything on top of it.

</details>

Q2. What does "OpenAI-compatible" buy us?

<details><summary>answer</summary>

The same request/response shape works across providers, so our client code barely changes if we swap models.

</details>

Q3. What is a smoke test?

<details><summary>answer</summary>

A tiny end-to-end check that the basics work at all — before testing any details.

</details>

---

## S1 — The bare reason → act → observe loop

**What we built.** `agent.py`: the simplest possible agent loop, with **no** reliability
features. Each turn:

1. **reason** — ask GLM what to do; it may reply with text or *call a tool*.
2. **act** — if it called a tool, run that tool. (`dispatch()` looks the tool up in a *registry*
   — a name→function dictionary — and runs it.)
3. **observe** — feed the tool's result back into the conversation, and loop.

Every step is written as one line to `trajectory.jsonl` (a *trajectory* = the full recorded
play-by-play of a run) so a human can read exactly what happened.

**Teaching note.** *Build the ugliest working version first.* S1 deliberately has **zero** help —
no retries, no fixing mistakes. That bareness is the **control group**: later you add one guardrail
at a time and measure the lift against this loop. No baseline, no measurement.

**New words.** *reason→act→observe loop*, *dispatch*, *registry*, *trajectory (JSONL)*, *baseline*.

**Recall — try before you reveal:**

Q1. What are the three phases of the loop, and what can go wrong in each?

<details><summary>answer</summary>

reason (model emits no tool call when one is needed, or an invalid one), act (the tool errors — bad input, exception, 404), observe (the loop never converges and runs out of steps).

</details>

Q2. Why deliberately leave out retries and error-recovery?

<details><summary>answer</summary>

So it's a clean baseline. You can only measure how much a guardrail helps by comparing to a version with no guardrails.

</details>

Q3. What is the trajectory file for?

<details><summary>answer</summary>

A line-by-line record of each run so a human can hand-read where it went wrong — the raw input to S3's failure triage.

</details>

---

## S2 — The real task + a deterministic oracle

**What we built.** Three pieces replace S1's placeholder weather task:

- `scenario.py` — the real task, packaged as **data** (a frozen `Scenario`). The task: *"find the
  grand total for order ORD-204."* The model must:
  1. call `get_order("ORD-204")` → learns `item_total = 140` and `ship_zone = "WEST"`,
  2. call `get_ship_rate("WEST")` → learns `rate = 18` *(a **chained** lookup — step 2 needs a
     value step 1 produced)*,
  3. call `submit_answer(158)`.

  The records live in small fixed tables, and the correct answer (140 + 18 = **158**) is computed
  separately in plain Python — that's the *ground truth*.
- `oracle.py` — the **deterministic oracle**: `grade(submitted, expected)` returns pass/fail by
  exact comparison. No AI involved. It's lenient about format (`"$158"` still counts) but rejects
  anything that isn't a real number.
- `agent.py` (generalized) — the same loop now drives *any* `Scenario`, and it recognizes the
  `submit_answer` **terminal tool**: when the model calls it, the loop grabs the number and stops.
  Each run ends one of three ways: `submitted`, `no_submit` (talked but never submitted), or
  `max_steps` (ran out of turns).

**Teaching note.** The deterministic oracle is what makes the whole project *measurable and
honest*. Ground truth is computed by a **separate** code path over the same records, the comparison
is mechanical, and the thing being graded (the model's tool-use) never influences its own grade —
so there's no circularity. An AI judge would import its own blind spots and randomness exactly where
we need a fixed ruler. (See `DECISIONS.md` D2 + D3.)

**New words.** *scenario (as data)*, *chained lookup*, *terminal tool*, *oracle*, *ground truth*,
*mechanical vs cognitive failure*.

**Recall — try before you reveal:**

Q1. Why is grading with another AI ("LLM judge") a bad idea here?

<details><summary>answer</summary>

Self-graded homework: the same class of system that can fail the task scores it, so its blind spots correlate with the task's, plus it adds flattery and randomness — a rubber ruler where you need a fixed one.

</details>

Q2. What makes S2's failures "mechanical" rather than "cognitive," and why does that matter?

<details><summary>answer</summary>

It's a chained lookup with trivial math, so failures are wrong-tool / wrong-field / skipped-step (mechanical, recoverable) rather than can't-do-the-math (cognitive). The thesis is that guardrails can recover the mechanical kind.

</details>

Q3. What happens if the model never calls `submit_answer`?

<details><summary>answer</summary>

The run stops as `no_submit` (or `max_steps`); the oracle sees no number and grades it False with reason "no_numeric_answer" — a clean mechanical failure S3 can count.

</details>

---

## S3 — Does a gap even exist? (kill-trigger, then inject)

**What we built.** The diagnostic that decides whether the whole thesis is worth building.

- `runner.py` — the **N-trial runner**: run the scenario many times for one **arm** (a configuration
  under test — here, one model) and report the raw **completion rate** (k/N), keeping every trajectory.
- We ran the GLM baseline: **20/20 = 100%** on the clean task — verified genuine (every win used both
  lookups in 3 turns; none guessed). A 100% baseline has *nothing* for a guardrail to recover, so
  **no natural gap exists** — the pre-registered **kill-trigger 1** fired.
- Rather than fake a gap, we **injected one honestly**: `faults.py` wraps the lookup tools to raise a
  deterministic, seeded **transient 503 error** at a set rate (`with_faults`). Re-diagnosing the
  baseline under rate-0.5 injection: **16/20 = 80%**. All 4 misses were `max_steps` — GLM persistently
  retried the 503'd tool, but each retry burned a turn against its 6-step budget. (See `DECISIONS.md`
  D12 + D13.)

**Teaching note.** Two ideas worth keeping. **(1) A pre-registered kill-trigger saves you from fooling
yourself.** We'd written down, in advance, "if GLM already passes ≳85%, don't build guardrails." When
it scored 20/20 we *honored* that, instead of rationalising a mechanism onto a gap that wasn't there.
**(2) When the natural gap doesn't reproduce, injecting faults is a legitimate pivot — if you say so
plainly.** We didn't pretend GLM is bad at the task; we built a *controlled fault-recovery testbed* (the
floor) and kept a tuned natural gap as a stretch. The injected fault also reveals the mechanism *lever*:
the bare loop's only recovery is the **model** retrying, which **eats its turn budget**; the coming
error-recovery guardrail retries at the **harness** level, transparently — so it rescues exactly these
`max_steps` failures.

**New words.** *arm*, *completion rate*, *fault injection*, *transient (503) error*, *kill-trigger*,
*controlled testbed*, *retry-exhaustion*.

**Recall — try before you reveal:**

Q1. GLM scored 20/20 on the clean task. Why was that *bad* news, and what did we do about it?

<details><summary>answer</summary>

A 100% baseline leaves no room for a guardrail to show a measurable lift — there's no gap to close (kill-trigger 1). Per the pre-commitment we did NOT build mechanisms; we injected deterministic mechanical faults (503s) to create a recoverable gap honestly, and reframed the headline to a "controlled fault-recovery testbed."

</details>

Q2. Under rate-0.5 injection the baseline dropped to 80%, and all 4 failures were `max_steps`. Why does a single failing trial fail?

<details><summary>answer</summary>

The tool 503s; the bare loop feeds the error back and GLM retries the call — but each retry consumes one of its 6 reasoning turns. When a trial's fault pattern needs more successful calls than the budget allows (e.g. seed 4: `get_order` 503'd all six turns), it runs out of steps with no answer → `max_steps`. It's *retry-exhaustion*: mechanical and recoverable (a harness-level retry that doesn't cost model turns would rescue it).

</details>

Q3. Both N=20 runs failed the *same* seeds {4, 9, 16, 18}. What does that tell us, and how do we get more statistical power?

<details><summary>answer</summary>

With deterministic per-trial seeds, completion is dominated by the fault *pattern*, not GLM's randomness — so "N" is the number of *distinct* seeds. Re-running the same 20 seeds is reproducibility, not more data (don't pool into "N=40"). For power: more distinct seeds (toward N=50) and/or a higher fault rate for a bigger gap.

</details>

---

## S4 — The first guardrail (error-recovery) + confidence intervals

**What we built.** S4 turns "run one arm, eyeball k/N" into "compare two arms and report the
*difference*, with honest error bars." Four pieces:

- **`agent.py` grew one toggle — `recover`.** This is the **error-recovery** guardrail. When a tool
  call hits a transient fault (a 503-style "temporarily unavailable"), the *harness* quietly retries
  it **inside the same step**, up to `max_recoveries` times, **without** spending one of the model's
  reasoning turns. `recover=False` is the bare baseline from S1/S3 — byte-for-byte unchanged. The
  contrast is the whole point: in the baseline the model itself has to notice the error and re-call
  the tool, burning a turn each time (that's how S3's runs died at `max_steps`); error-recovery makes
  the retry free of turns. It retries only *transient* errors — a malformed call or an unknown-id
  error is permanent, so re-calling it identically would just waste attempts (those want a different
  guardrail).
- **`stats.py` — the honest rulers.** `wilson(k, n)` gives one arm's rate a **Wilson interval** (the
  believable range for the true rate given only n tries; it behaves at the 0%/100% edges, where the
  textbook mean ± std interval falls apart and can even point outside 0–100%). `newcombe_diff(...)`
  gives the **difference** between two arms its own interval. `excludes_zero(lo, hi)` is the gate: if
  the difference interval includes 0, we are *not allowed* to call it a win.
- **`ablation.py` — the two-arm harness.** Runs **baseline** and **+error-recovery** over the *same*
  injected faults (trial i uses the same `seed=i` for both arms — a **paired** comparison), then
  prints each arm's rate + Wilson interval, the gap between them + Newcombe interval, and a one-line
  verdict: a real result (interval clears 0) or "not a result" (it straddles 0).
- **Tests for all of it** — `test_stats.py` (CI math pinned to hand-computed values), `test_recover.py`
  (the retry logic + an end-to-end loop run driven by a fake model), `test_ablation.py` (the two-arm
  plumbing). All offline, all green.

**The measured result.** The live run (`uv run ablation.py z-ai/glm-4.6 40 0.6`, GLM-4.6):
**baseline 27/40 = 67.5%** (Wilson 95% CI [52.0%, 79.9%]; all 13 misses were `max_steps`
retry-exhaustion) vs **+error-recovery 40/40 = 100%** (Wilson 95% CI [91.2%, 100%]; the harness
silently absorbed **104** transient 503s, spending no model turns). **Gap closed: +32.5%, Newcombe
95% CI [+17.3%, +48.0%]** — the interval clears 0 *and* the two Wilson bars don't overlap, so it's a
*real* result by our honesty rule, not a coincidence of small N. (See DECISIONS D17.) Note 100% is a
boundary: the honest read of the mechanism arm is its Wilson floor (91.2%), not "certainly perfect."

**Teaching note.** Two ideas worth keeping. **(1) Put the cost of a retry where it doesn't hurt.** The
bare loop *already* retries — the model re-calls the broken tool — but every retry eats a scarce
reasoning turn, and under heavy faults that's exactly what kills the run. Error-recovery doesn't add
retrying; it *moves* it to the harness, where a retry costs no turn. The lesson generalises: often the
fix isn't "do a new thing," it's "do the same thing somewhere cheaper." **(2) A difference needs its
own error bar.** It's tempting to draw two rate bars and check whether they overlap — but the thing
we're claiming is the *gap*, a single quantity, so it gets its own interval (Newcombe). If that
interval straddles 0, the gap could be nothing, and we say so. That honesty gate is the line between a
*measurement* and a marketing number.

**New words.** *error-recovery*, *retry-nudge*, *harness-level retry*, *Wilson interval*, *Newcombe
interval*, *point estimate*, *straddles zero / excludes zero*, *ablation*, *arm-as-config*, *paired
comparison*.

**Recall — try before you reveal:**

Q1. The baseline loop already retries a 503'd tool (the model re-calls it). So what does
error-recovery actually *change*, and why does that rescue S3's `max_steps` failures?

<details><summary>answer</summary>

It moves the retry from the *model* to the *harness*. In the baseline each retry is a fresh model turn (the model sees the error, then decides to re-call), so a burst of 503s burns through the 6-turn budget and the run dies as `max_steps`. Error-recovery retries the call *inside the same step*, spending no model turn — so transient faults get absorbed before they can exhaust the budget. Same retrying, cheaper place.

</details>

Q2. Why report a **Newcombe interval on the difference** instead of just drawing the two arms' Wilson
bars and seeing whether they overlap?

<details><summary>answer</summary>

The thing we're claiming is the *gap* — one number — so it needs its own uncertainty. Two Wilson bars that merely touch or barely overlap don't cleanly answer "could the true gap be zero?": non-overlapping bars are sufficient to declare a difference but not necessary, so eyeballing overlap can hide a real effect (or a null). Newcombe builds the interval *for the difference itself*; if it includes 0 we report "no clear effect" — the honest gate (D7/D16).

</details>

Q3. Both arms run trial i with the same `seed=i`. Why pair them like that, and what does pairing
*not* fix?

<details><summary>answer</summary>

Pairing means both arms face the *identical* fault pattern on trial i, so the gap between them can't be an artifact of one arm simply drawing easier faults — it isolates the mechanism's effect. What it doesn't fix: GLM is still stochastic, so the two arms may make different numbers of tool calls and land on different draws within that pattern. That residual randomness is real — which is exactly why we still need N *distinct* seeds and confidence intervals, not a single paired run.

</details>

---

## S5 — The deliverable: drawing the gap-closure chart

**What we built.** S5 turns S4's measured numbers into the project's one headline picture — the
**gap-closure chart** — and nothing more. No new model runs: `chart.py` reads the *saved* S4 result
and draws it. Three pieces:

- **The data, vendored.** S4 wrote its result to `runs/ablation-summary.json`, but `runs/` is
  *git-ignored* (it's scratch output), so it wouldn't survive a fresh clone. We **vendored** it —
  committed a copy to `docs/figures/gap-closure-data.json` — so the figure regenerates from numbers
  that live *inside* the repo, with no paid re-run. That file is the chart's single source of truth.
- **`chart.py` — the renderer.** Two bars, **Baseline (no mechanism)** vs **+ Error-recovery**, on a
  0–100% axis. Each bar carries its **Wilson 95% CI** as a *whisker* (the small vertical line showing
  the honest range around the height) and a `k/N` + percent label; a two-headed arrow between the bar
  tops is annotated with the **+32.5%** gap and its **Newcombe 95% CI [+17.3%, +48.0%]**. The
  load-bearing bit is the caption printed *on the figure*: `gap is INJECTED (controlled fault-recovery
  testbed) · 104 transient 503s absorbed`. The chart must never be mistakable for a natural-gap result.
- **`test_chart.py` — offline guards.** The pure label/format helpers (no matplotlib) are pinned to
  exact strings, and one test asserts the vendored data still matches the S4 / D17 numbers — so the
  figure can't silently drift to plotting something we didn't measure. The render itself is
  smoke-checked by running `chart.py`. All **seven** offline suites stay green.

**The output.** `uv run chart.py` writes the committed `docs/figures/gap-closure.png`, embedded in
`README.md` §7: baseline **67.5%** → +error-recovery **100%**, gap **+32.5%**, the interval clears 0
— the same result as D17, now legible at a glance.

**Teaching note.** Two ideas. **(1) A figure is an argument, so it must carry its own caveats.** The
single most important mark on this chart isn't a bar — it's the word *INJECTED* in the caption. A
reader who sees "67.5% → 100%" and walks away believing GLM is naturally that unreliable has been
misled; the honesty rule (say the gap is manufactured) has to travel *with* the picture, not sit in a
doc they won't open. **(2) Don't let your deliverable depend on scratch.** The real numbers lived in a
git-ignored `runs/` file; if the chart read straight from there, anyone cloning the repo (or you,
after a cleanup) couldn't rebuild it. Vendoring a tracked copy makes the artifact *reproducible from
the repo alone* — and the test pinning that copy to D17 keeps the convenience from becoming a lie.

**New words.** *gap-closure chart*, *deliverable*, *vendoring*, *error bar / whisker*, *annotation*,
*headless rendering (Agg)*, *DPI*.

**Recall — try before you reveal:**

Q1. The S4 numbers already existed in `runs/ablation-summary.json`. Why copy them into a tracked
`docs/figures/gap-closure-data.json` instead of just reading the original?

<details><summary>answer</summary>

Because `runs/` is git-ignored — it's scratch output that isn't committed, so it wouldn't exist after a fresh clone (or a cleanup). *Vendoring* a tracked copy makes the figure regenerable from the repo alone, with no paid re-run. And `test_chart.py` pins that copy to the D17 numbers, so the convenience can't quietly drift into plotting the wrong values.

</details>

Q2. The +error-recovery bar sits at 100%, yet the chart still draws a whisker hanging *below* it. Why
isn't a 100% bar just a clean line at the top?

<details><summary>answer</summary>

Because 100% is 40/40 on only N=40 — the *true* rate could still be a little under 100%; we just didn't see a failure in 40 tries. The Wilson interval reflects that: [91.2%, 100%]. So the honest read of the bar is its floor, 91.2%, which is exactly what the lower whisker shows. The upper whisker is zero-length (you can't exceed 100%), giving the one-sided look. A bar with no whisker would over-claim certainty.

</details>

Q3. What is the single most important thing printed on this figure, and why does it matter more than
any bar?

<details><summary>answer</summary>

The caption word **INJECTED**. The bars show a big, real gap-closure — but it was measured against faults we *manufactured* (seeded 503s), not failures GLM produces on its own. Per the project's honesty rule, a figure that could be mistaken for a *natural* gap is misleading. The caption makes the manufactured nature travel with the picture, so the result can't be over-read when the chart is lifted out of its doc.

</details>

---

## Glossary

Terms are added the first time they appear. If one's missing or unclear, that's a doc bug — flag it.

- **API** — the agreed way one program asks another for something (here, how our code asks the model for a reply).
- **OpenAI-compatible / OpenRouter** — OpenRouter resells many models behind the same request shape OpenAI uses, so one client works for all of them.
- **tool-calling** — the model, instead of answering in prose, emits a structured request to run a named function with arguments (e.g. `get_order(order_id="ORD-204")`).
- **tool / function schema** — the JSON description we show the model of a tool: its name, what it does, its arguments.
- **registry** — a dictionary mapping a tool's name to the actual Python function that runs it.
- **dispatch** — look up the tool the model asked for in the registry and run it; report success or an honest error.
- **reason → act → observe loop** — the agent cycle: decide (maybe call a tool) → run the tool → feed the result back → repeat.
- **trajectory (JSONL)** — the full line-by-line record of a run (`trajectory.jsonl`); JSONL = "one JSON object per line."
- **scenario (as data)** — a task bundled as a value (tools + records + the question + the known answer) so one loop can run many different tasks.
- **chained lookup** — a multi-step lookup where a later step needs a value an earlier step produced.
- **terminal tool** — a tool whose only purpose is to end the task and hand over the final answer (`submit_answer`).
- **oracle** — code that already knows the correct answer and returns pass/fail. Never an AI here.
- **ground truth** — the known-correct answer, computed independently of the model.
- **deterministic** — same input always gives the same output (the oracle); opposite of stochastic.
- **stochastic** — involves randomness, so the same input can give different outputs (the model).
- **temperature** — the knob for how random the model's output is (0 = most predictable).
- **mechanical failure** — the machinery of a step broke (bad call, wrong record, malformed arguments) — recoverable.
- **cognitive failure** — the model genuinely couldn't reason the answer out — not what this project targets.
- **baseline** — the no-help version you measure improvements against (S1's bare loop).
- **guardrail / mechanism** — a reliability feature added on top of the baseline (retry-nudge, error-recovery).
- **proportion / confidence interval** — success is a *proportion* (k of N); a CI is the honest range the true rate likely sits in. Built in S4: **Wilson** per arm, **Newcombe** on the difference (`stats.py`).
- **ablation** — turning one factor on/off (here, the error-recovery guardrail) while holding everything else fixed, to measure that one factor's effect. Built in S4 (`ablation.py`).
- **arm** — one configuration under test in a run (a model, or baseline vs +error-recovery). In S4 an arm is *config* — `{label, run_kwargs}` — so the harness can drive several through one loop.
- **arm-as-config** — representing an arm as data (a label + the kwargs that toggle its mechanism) rather than hard-coding it, so adding an arm is a list entry, not a rewrite.
- **error-recovery** — the S4 guardrail: the *harness* retries a transient tool failure inside the same step, spending no model turn. The `recover=True` arm.
- **retry-nudge** — a *different* guardrail (S5+): re-prompt the *model* to try again after a failure — which still costs it a turn. Built as a sibling toggle later.
- **harness-level retry** — a retry done by the surrounding code (the harness), not the model, so it consumes no reasoning turn. The mechanism behind error-recovery.
- **max_recoveries** — the cap on how many harness-level retries one tool call may use before the loop gives up and feeds the error back to the model.
- **Wilson interval** — the believable range for *one* proportion (an arm's pass-rate) given only N samples; stays inside [0, 1] and behaves near 0%/100%, where a ±std interval breaks.
- **Newcombe interval** — the believable range for the *difference* between two proportions (the gap between arms); built by combining the two arms' Wilson intervals ("square-and-add").
- **point estimate** — the single best-guess number (e.g. the raw gap = mechanism rate − baseline rate) *before* you attach an interval to it.
- **straddles zero / excludes zero** — a difference interval that includes 0 *straddles* it (can't claim an effect — the honesty gate); one entirely above or below 0 *excludes* it (a real effect).
- **paired comparison** — running both arms against the *same* per-trial fault pattern (same seed i), so the measured gap isn't contaminated by one arm drawing luckier faults.
- **completion rate** — the fraction of trials that finish correctly (k/N); the project's headline number.
- **fault injection** — deliberately, reproducibly making a tool fail sometimes (a seeded 503) so there's a recoverable failure to measure guardrails against.
- **transient (503) error** — a tool failure that may succeed if you simply retry it.
- **kill-trigger** — a pre-agreed "stop and change course" condition, fixed in advance so a result you don't like can't be rationalised away.
- **controlled testbed** — measuring guardrails against faults you injected on purpose (and disclose), rather than a naturally-occurring gap.
- **retry-exhaustion** — failing because retries (each costing a turn) used up the step budget before the task could finish.
- **gap-closure chart** — the project's headline figure: how far a guardrail lifts completion above the no-mechanism baseline, drawn with confidence intervals. Built in S5 (`chart.py`).
- **deliverable** — the one concrete artifact a project exists to produce (here, the gap-closure chart).
- **vendoring** — committing a copy of an otherwise-uncommitted (git-ignored) file into the repo, so a build doesn't depend on something that isn't tracked.
- **error bar / whisker** — the small vertical line drawn on a bar to show its confidence interval: the honest range around the plotted height.
- **annotation** — text or an arrow added to a chart to call out a specific value (here, the +32.5% gap and its Newcombe interval).
- **headless rendering (Agg)** — drawing a figure straight to an image file with no on-screen window (matplotlib's "Agg" backend), so it works in a script or on a server.
- **DPI (dots per inch)** — the resolution of a saved image; higher DPI means more pixels and a crisper PNG.
