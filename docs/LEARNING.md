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

## S6 — The second guardrail (retry-nudge) — and a measured null

**What we built.** S6 added the project's *second* guardrail and the fault it's meant to fix — then
measured it honestly and got a **null**, which turned out to be the interesting part.

- **A new fault: the malformed call (`faults.py` → `with_malformed_faults`).** The S3 fault was a flaky
  *service* (a transient 503 — the call is fine, the tool hiccups). A malformed call is a bad *call*: the
  model used the wrong argument. An "armed" tool rejects the documented parameter (`order_id`) with an
  informative hint — `400 … use 'id' instead` — and only a *corrected* call clears it. Two properties make
  it the right test for retry-nudge: it's **permanent** (the error string isn't "retryable", so
  error-recovery's harness-retry ignores it) and **sticky** (armed once per seed+tool, so a blind resend
  keeps failing — only a genuine correction works). Why sticky? Because the 503 redraws a fresh coin each
  call, so *any* resend clears it; a malformed call must require the caller to actually *change* the call,
  or we'd be measuring luck instead of correction.
- **A new guardrail: retry-nudge (`agent.py` → the `nudge` toggle).** On a failed tool call, the harness
  appends one explicit corrective re-prompt ("that failed — don't repeat it, fix the arguments and call
  again"). The load-bearing contrast with error-recovery: a nudge spends a **model turn** (the model
  re-reasons), so it can fix a *malformed* call a blind harness retry never could — at the cost of a turn.
- **A bigger harness + chart, same old figure.** Two arms became *N*: `ablation.run_arms` runs any list of
  arms over one shared fault and gives each a Wilson CI + a Newcombe gap vs the baseline; `run_ablation`
  now just calls it and repackages the result into the *exact* old 2-arm shape, so the S4/S5 chart and its
  vendored data never moved (generalise at the seam, don't disturb what shipped). `chart.build_multi_figure`
  draws *N* bars, coloured by the **measured verdict** (teal = a real lift, steel = a null) so the picture
  can't over-claim.

**The result — a clean null, and why that's the point.** Three arms on the malformed testbed (GLM-4.6,
N=20): **baseline 100% · +error-recovery 100% · +retry-nudge 100%**. Both gaps **+0.0%**, Newcombe
**[−16.1%, +16.1%]** → straddles 0 → null. The trajectories show why: GLM-4.6 reads the `use 'id'` hint
*as a tool result* and corrects its own call on the very next turn, unaided — so the explicit nudge (which
fired 26 times) has nothing to add, and error-recovery can't engage at all. A cheap **pilot** (N=6) caught
this *before* we paid for the full run.

**Teaching note.** Two ideas. **(1) A null is a result — sometimes the best one.** We didn't get a bar to
brag about; we got a *boundary*: a guardrail earns its keep only where the model **can't help itself**.
That even sharpens S4 — error-recovery's +32.5% wasn't "fixing errors" in general, it was rescuing
**turn-exhaustion** (transient faults made GLM retry until it ran out of steps). Malformed calls don't
exhaust turns, so no guardrail is needed. Knowing *why* a guardrail worked tells you exactly where it
won't. **(2) De-risk an expensive measurement with a cheap one.** The N=6 pilot cost ~18 trials and told
us the full run would be flat — spend a little to learn whether it's worth spending a lot, especially
before burning API credits on a result you can preview.

**New words.** *malformed call*, *sticky fault*, *permanent (non-retryable) error*, *self-correction*,
*null result*, *guardrail specificity*, *N-arm ablation*, *pilot run*.

**Recall — try before you reveal:**

Q1. The 503 fault is a fresh coin-flip on every call, but the malformed fault is "sticky" — armed once per
seed+tool. Why does retry-nudge *need* the malformed fault to be sticky?

<details><summary>answer</summary>

Because the whole point is to measure whether the model *corrects* its call. If the malformed fault redrew per call like the 503, a blind identical resend would clear it by luck — so a model that just repeats the same wrong call would "pass," and we'd be measuring chance, not correction. Sticky means only a genuinely *changed* (corrected) call succeeds, so a pass really reflects the model fixing its arguments — exactly the behaviour retry-nudge is supposed to encourage.

</details>

Q2. Error-recovery and retry-nudge are both "retry" guardrails. Why does error-recovery do *nothing*
against a malformed call, while it closed a +32.5% gap against the 503?

<details><summary>answer</summary>

Error-recovery only retries *transient* errors (it checks the error string for "503 / timeout / retry"-style hints) and it re-calls the tool *identically*, spending no model turn. A 503 clears on an identical retry (the service just hiccupped). A malformed call is a *permanent* error — re-sending the identical wrong call fails again — and its `400 invalid_argument` string isn't classified as retryable, so error-recovery doesn't even try. Fixing it requires *changing* the call, which only the model can do (a model turn) — that's retry-nudge's job, not error-recovery's.

</details>

Q3. All three bars are at 100% — a null. Why is that still a worthwhile result, and what does it tell you
about *when* a guardrail helps?

<details><summary>answer</summary>

It marks a boundary: a guardrail helps only where the model **can't help itself**. GLM-4.6 self-corrects malformed calls from the tool-error hint, so neither retry guardrail adds anything. That clarifies what S4 actually measured — error-recovery's +32.5% was specifically *turn-exhaustion* recovery (transient faults made the model retry until it ran out of steps), not a general "fixes errors" power. Malformed calls don't exhaust turns, so there's nothing to rescue. A measured null, reported honestly, is exactly the kind of result the project's honesty rule exists to protect.

</details>

---

## S7 — The natural-gap hunt: does GLM break on its own? (a measured no)

**What we built.** S7 chased the project's headline goal (DECISIONS D12): stop *injecting* faults and
instead **harden the task itself** until GLM-4.6 fails on its own mechanical merits — then see whether the
existing guardrails close that *natural* gap. Three pieces, all **pilot-gated** so we'd spend little before
learning anything:

- `scenario_hard.py` — a **hardened task**, built as a new `Scenario` so the frozen S2 task (and the shipped
  S5 figure) stays untouched. *v1:* a 4-lookup chain — `find_orders` (the customer has several orders, so the
  model must **disambiguate** by zone) → `get_order` → `get_ship_rate` → `get_customer_discount` — through 15
  look-alike records (`ORD-204` / `ORD-240` / `ORD-024`…). *v2 (the escalation):* a deeper 5-lookup chain
  (adds a per-zone tax) through ~25 records with a **near-duplicate-customer** distractor ("Globex" vs "Globex
  Labs", each with its own EAST order). The arithmetic stays trivial on purpose — every added difficulty is a
  place to thread/pick the *wrong value* (mechanical), not to out-think hard math (cognitive).
- `pilot.py` — a **clean** (no injected faults), bare-baseline runner: the cheap de-risk that asks one
  question — *does the hardened task break GLM, and of what type?* — before any full experiment.
- `test_scenario_hard.py` — 40+ offline checks (ground truths 82 and 117, unique targets, the distractor, the
  full tool chains, wiring) so the scenario is proven correct before a single API call.

**The result — a measured "no".** v1 pilot: **8/8 = 100%**. Per a pre-agreed **bounded escalation** (push
difficulty up *once*; if GLM still scores ≥7/8, stop — no endless chase), v2 pilot: **8/8 = 100%** again.
Every run submitted the exact ground truth. So we **declared done**. Across four independent probes — 20/20
clean (S3), self-heals malformed (S6), 8/8 hard-v1, 8/8 hard-v2 (S7) — **GLM-4.6 shows no measurable natural
gap at reasonable mechanical difficulty.** To study guardrails on this model you must *inject* faults, exactly
as S3–S6 did and disclosed.

**Teaching note.** Two ideas worth keeping. **(1) Guardrails are *typed* — and a strong model's natural
failures are the wrong type for the ones we have.** Error-recovery fixes *transient* errors; retry-nudge fixes
*malformed* calls. Both only ever fire on a tool-call **error**. But when a hard task breaks a strong model, it
usually does so by **submitting a wrong number with no error at all** (wrong record, wrong field, a dropped
term) — a *validation* gap that neither guardrail can even see. So "harden the task and re-run the guardrails"
was structurally unlikely to produce a win even *if* GLM had slipped: a found natural gap would have reopened
"should we build a *third* (validation) guardrail?", not rescued the two we have. Knowing the *type* of failure
a tool fixes tells you, in advance, which gaps it can't touch. **(2) A pre-committed stop rule turns a chase
into a decision.** "Hunt for a gap" has no natural end — you can always make a task harder. Writing the stop
down in advance ("escalate *once*; ≥7/8 → declare done") let a *negative* result be a clean, honest finish
instead of an open-ended money pit. A confident "it doesn't break, and here's the evidence" is a result.

**New words.** *natural gap*, *validation gap / guardrail*, *failure triage*, *bounded escalation*, *at
ceiling*, *robustness signal*.

**Recall — try before you reveal:**

Q1. We hardened the task hoping GLM would fail "mechanically." Even if it *had* failed, why would the existing
guardrails (error-recovery, retry-nudge) probably still measure a null?

<details><summary>answer</summary>

Because both guardrails only fire on a tool-call *error* (transient → error-recovery; malformed → retry-nudge). A hard task's natural failures are mostly *wrong-answer-no-error* — the model picks the wrong record/field or drops a term and submits a wrong number, with no error to trigger anything. That's a *validation* gap, which neither existing guardrail can see. So a found natural gap would have pointed to a new (validation) guardrail, not rescued the two we have.

</details>

Q2. The v1 pilot was 8/8. Why escalate to v2 instead of either declaring done immediately or chasing harder and
harder?

<details><summary>answer</summary>

A single difficulty proves little, but an open-ended "make it harder until it breaks" is a money pit. So we pre-committed a *bounded escalation*: push difficulty up exactly once (v2: deeper chain + more confusable records + a distractor), then apply a hard stop — if GLM still scores ≥7/8, declare done. v2 was 8/8, so we stopped. The rule turns "when do we give up?" from a sunk-cost judgment in the moment into a decision made in advance.

</details>

Q3. S7 found *no* gap. In what sense is that a real, defensible result for the project rather than a failure?

<details><summary>answer</summary>

It's the honest cap on the headline goal: across four probes GLM-4.6 doesn't produce a measurable natural gap at reasonable mechanical difficulty, so the *only* honest way to study reliability guardrails on this model is to inject faults — which is exactly what S3–S6 did and disclosed. The injected fault-recovery testbed (error-recovery's +32.5% real lift, retry-nudge's honest null) is therefore the project's legitimate deliverable, and "a strong open model is robust here" is itself a finding worth stating plainly.

</details>

---

## S8 — A weak model's natural gap, and a guardrail that closes it (+75 pp)

**What we built.** S7 proved GLM-4.6 never breaks on its own — but was the *task* unbreakable, or is GLM just
strong? S8 settles it by changing the one variable we hadn't: the **model**. Hold the task fixed and **clean**
(no injected faults) and swap GLM-4.6 for a *weaker* model. Three pieces:

- A quick **scout** of OpenRouter (254 of 338 models expose tool-calling; the tiny 1–3B ones don't, so the
  "too weak to even tool-call" floor partly takes care of itself), then **fit pilots** on two weak models.
- `weak_ablation.py` — a clean 3-arm ablation (baseline / +retry-nudge / +submit-nudge) over the frozen S2 task
  with **no fault injection at all** (`fault_kind="none"`).
- **submit-nudge** — a NEW guardrail in `agent.py` (the `submit_nudge` toggle), test-driven via
  `test_submit_nudge.py`: when a turn ends in prose with **nothing submitted**, re-prompt the model to actually
  call `submit_answer`, then continue — instead of ending the run.

**What the pilots found — a capability cliff.** Neither weak model failed the way we pre-registered (a
*malformed call*). Instead each failed a *different* non-tool-error way, both scoring 0/16:

- **`llama-3.1-8b`** retrieves the data but **hallucinates the final number** — it had `140` and `18` in hand and
  still submitted `1234.56`, even submitting a literal formula string. A *validation* failure (parked).
- **`mistral-nemo`** computes the right answer (`158`) and then **never calls the terminal tool** — it narrates
  "calling submit_answer…" and stops. A *protocol* / **no-submit** failure — the one submit-nudge targets.

**The result — the first *natural* gap-closure.** Clean 3-arm ablation, mistral-nemo, **N=20**:
**baseline 0% · +retry-nudge 0% (a null — it fires 0 times, because a no-submit isn't a *failed* call) ·
+submit-nudge 75%**. Gap **+75.0 pp, Newcombe 95% CI [+47.8, +88.8]** — clears 0, and the Wilson bars don't
overlap. Figure: `docs/figures/weak-gap.png`.

**Teaching note.** Two ideas. **(1) Guardrail specificity, now in one picture.** The same experiment runs the
*wrong* guardrail (retry-nudge) and the *right* one (submit-nudge) side by side: the wrong one does literally
nothing — it never even fires — and the matched one lifts completion from 0% to 75%. A guardrail isn't "more
reliability" in general; it closes *one named failure* and is blind to the others. **(2) The result that matters
is the *interaction*, not the model.** This is **not** "mistral-nemo is bad." It's that a *weak-but-tool-capable*
model has a natural failure (it forgets to pull the terminal trigger) that a strong model (GLM-4.6, S6/S7) simply
doesn't — so the guardrail that's worthless on GLM is worth +75 pp here. The honest residual proves the point:
submit-nudge made the model *submit* every time, but 5/20 of those were a wrong `140` (shipping forgotten) — a
*validation* gap it can't touch, which is the next experiment.

**New words.** *submit-nudge*, *protocol gap / no-submit*, *capability cliff*, *bifurcation*, *fit pilot*,
*capability × guardrail interaction*.

**Recall — try before you reveal:**

Q1. On mistral-nemo, the +retry-nudge arm measured an exact 0.0 pp gap and fired **zero** nudges, while
+submit-nudge lifted completion to 75%. Both are "nudge the model" guardrails — why did one do nothing and the
other work?

<details><summary>answer</summary>

They target different failures. Retry-nudge only fires after a *failed tool call* (it re-prompts "that call errored — fix it"). mistral-nemo's failure isn't a failed call; it's a *missing* one — it computes 158 and never calls submit_answer at all, ending the turn in prose. With no failed call, retry-nudge never triggers (0 nudges, 0 effect). Submit-nudge fires on exactly that condition — "you ended without submitting" — and re-prompts the model to call the terminal tool, which it then does. Same idea (re-prompt the model), different trigger; only the trigger that matches the failure helps. That's guardrail specificity.

</details>

Q2. S8's headline is +75 pp on mistral-nemo, but S6/S7 showed guardrails do little for GLM-4.6. Isn't that a
contradiction? What is S8 actually claiming?

<details><summary>answer</summary>

No contradiction — S8's claim is about the *interaction* between model capability and a guardrail, not about guardrails in general. A strong model (GLM-4.6) reliably calls the terminal tool, so a submit-nudge has nothing to do → no gap to close (consistent with S6/S7). A weaker-but-tool-capable model (mistral-nemo) reliably computes the answer but often forgets to submit it → a real natural gap a submit-nudge closes (+75 pp). The finding is "which capability level needs which guardrail," not "mistral-nemo is bad" or "guardrails always help."

</details>

Q3. submit-nudge took mistral-nemo from 0% to 75% — but why not to ~100%, and what does the leftover tell us?

<details><summary>answer</summary>

Because there are *two* natural failures stacked here. Submit-nudge fixes the *protocol* gap — the model not calling the terminal tool — and it fixed it completely (every run submitted). But ~5/20 of those submissions were `140` (item total with shipping forgotten): a *validation* gap — a wrong answer with no error. Submit-nudge makes the model submit; it can't make the arithmetic right. The residual ~25% is exactly the wrong-answer failure that a *validation* guardrail (the parked next experiment) would target — the same failure type S7's analysis flagged.

</details>

---

## S9 — The validation guardrail: submit *right*, not just submit (+25 pp)

**What we built.** S8 ended one guardrail short: submit-nudge got mistral-nemo to *submit*, but ~25% of the
time it submitted `140` — the item total with shipping silently forgotten. No tool errored; the model just
summed wrong. That's the **last** failure type the project hadn't closed: *wrong answer, no error*. S9 builds
the fourth and final guardrail for it — **validation** — plus its stacked experiment:

- **validation** — a new `validate` toggle in `agent.py`. When the model calls `submit_answer(value)`, before
  accepting it the harness calls `scenario.validate(...)`, which **recomputes the total from the model's own
  retrieved tool results** and, if `value` doesn't match, re-prompts ("your `140` doesn't match — the total
  must add both the item total `140` *and* the shipping `18`; recompute and resubmit") and keeps looping.
- `scenario.validate` in `scenario.py` — the recompute function, test-driven via `test_validation.py` (12 tests).
- `validation_ablation.py` — the **stacked** 2-arm experiment (submit-nudge reference vs +validation) on the
  clean task, and a new `validation-gap.png` figure (`chart.py`).

**The honest hard part — validate *without* the answer key.** The obvious objection: the oracle already knows
the answer is `158`; if the validator computes the same thing, haven't you just smuggled the answer key into the
agent and forced 100%? The answer is **no**, and the difference is *what each one reads*:

- the **oracle** computes from the **canonical records** (the true order) — authoritative, unfoolable;
- the **validator** computes from **whatever the model actually retrieved this run** — so it can be *fooled* by
  a wrong-record retrieval (it would happily accept a self-consistent-but-wrong total; the oracle still fails it).

So it's a **self-consistency check** ("does your answer match the evidence *you* gathered?"), not an answer key.
Its blind spot (wrong retrieval → self-consistent wrong answer) is the very thing that keeps it honest — it can
only close the *arithmetic-slip* slice of the wrong-answer gap, not manufacture a pass. Two bright lines the code
holds: it **never reads `scenario.ground_truth`**, and the re-prompt names the parts (`140`, `18`) but **not** the
sum `158`, so the model still does the addition itself — a *checker*, not a *solver*.

**Why "stacked."** mistral-nemo's bare baseline is 0% (it never submits), so there's *nothing to validate* until
submit-nudge lifts it into view. The clean controlled comparison therefore **holds submit-nudge fixed and toggles
validation** — the "baseline" for this ablation is itself the submit-nudge arm.

**The result.** Pilot-gated (N=8: validation fired on the one `140` it saw and lifted 75%→100%), then the full run
on **mistral-nemo, N=40**: **submit-nudge (reference) 75% · +validation 100%**, gap **+25.0 pp, Newcombe 95% CI
[+11.1, +40.2]** — clears 0, non-overlapping Wilson bars, a **real** result. Across pilot + full, validation fired
on **6/6** of the `140`s it ever saw and converted **every one** to a genuine `158`. The full ladder on this model
is now **0% → 75% → 100%**, and the matched-guardrail thesis is complete.

**Teaching note.** The keeper idea: **a self-check can be rigorous without being an oracle.** The temptation with a
"validate the answer" guardrail is to check against the truth — but that's circular (you can't deploy a checker that
already knows the answer). The honest version checks the answer against the model's *own evidence*: cheap, deployable
in the real world (you rarely have ground truth at run time, but you always have what the agent just fetched), and it
has a *principled* blind spot you disclose rather than hide. The +25 pp it measures is exactly "how much of the
wrong-answer gap was the model fumbling arithmetic it had the pieces for" — an honest, bounded claim.

**New words.** *validation guardrail*, *self-consistency check*, *stacked ablation*, *scaffolding*, *incremental
(marginal) lift*.

**Recall — try before you reveal:**

Q1. Why is recomputing the total *inside the agent* not "cheating," given the oracle grades against the same
`158`?

<details><summary>answer</summary>

Because the two compute from different inputs. The oracle reads the *canonical records* (the true order) — it's authoritative and can't be fooled. The validator reads only *what the model retrieved this run* — so if the model had fetched the wrong record, the validator would recompute a self-consistent *wrong* total and accept it (the oracle would still fail it). It's a *self-consistency* check ("does your answer match your own evidence?"), not an *answer* check ("is your answer the truth?"). It never reads `scenario.ground_truth`. So it can't force a pass — it only catches the case where the model had the right pieces and summed them wrong.

</details>

Q2. Why was the validation experiment *stacked* on submit-nudge (75% reference → 100%) instead of run against the
bare 0% baseline like S8?

<details><summary>answer</summary>

Because on the bare baseline mistral-nemo never submits (0%) — so there's no submitted answer for a validator to check. The validation gap is *masked* by the no-submit gap: you can't measure "does it submit the *right* number" until you've first got it to submit at all. Submit-nudge is the scaffolding that exposes the validation failure; the honest controlled comparison holds submit-nudge fixed and toggles only validation, so the +25 pp is validation's *own* (incremental) contribution, not the two guardrails' combined lift.

</details>

Q3. The +25 pp gap is smaller than S8's +75 pp. Why did we run N=40 instead of N=20, and how did we decide that
*before* spending?

<details><summary>answer</summary>

Because the effect is smaller, the confidence intervals have to be tighter to prove it's real. Using `stats.py` up front, we checked: at N=20 the result is knife-edge — 75%→100% clears zero only by a hair, and if validation caught just 4 of every 5 slips (75%→95%) the Newcombe interval would straddle 0 → a null. At N=40 it clears zero even in that 4-of-5 case. The binding constraint on this project is the statistics (the noise floor), not the code — so a smaller effect needs a bigger N, and mistral-nemo is cheap enough to just pay for it. (A cheap N=8 pilot still ran first, only to confirm the mechanism fires and lifts at all.)

</details>

---

## S10 — The blind spot, measured: validation on a *messy* gap (+45 pp, and the 55% it can't touch)

**What we built.** S9 proved the validation guardrail on its *best-case* testbed: mistral-nemo's wrong answers
were pure arithmetic slips on correctly-retrieved data, so the self-consistency check caught every one (100%).
S10 is the stress test (DECISIONS D23): the **same guardrail, byte-for-byte**, on **llama-3.1-8b** — a model
whose natural failure is **hallucination** (it submits made-up numbers like `1234.56`, or even the literal
formula string `"item_total_usd + ship_rate"`, even when the right data is in hand). New code was deliberately
tiny:

- `VALIDATION_ONLY_ARM` in `ablation.py` — validation **un-stacked** (no submit-nudge underneath). llama,
  unlike nemo, *does* call `submit_answer` on its own (with garbage), so nothing masks the wrong-answer gap
  and the reference arm is the bare baseline again.
- `hallucination_ablation.py` — the thin 2-arm runner (mirrors `validation_ablation.py`), plus the
  `hallucination-gap.png` figure in `chart.py`.
- A real **harness fix** llama forced on us: it sometimes emits tool arguments as a JSON *array* (`["ORD-204"]`
  instead of `{"order_id": "ORD-204"}`). That parses as valid JSON, but Python can't use a list as keyword
  arguments — and the old code treated "JSON parsed" as "arguments OK," so the submit path crashed mid-run.
  The fix routes any non-object arguments through the *existing* malformed-arguments path (honest error back
  to the model), with two regression tests. Crucially it adds **no help** — the model's bad call stays the
  model's failure; it just no longer crashes *our* code.

**The result.** Pilot (N=8: fired 3×, lifted 0/8 → 3/8 — and one run showed the validator being *fooled*, more
below), then the full run at **N=40** (sized with `stats.py`: at N=20 one lucky baseline `158` would turn the
result into a null): **baseline 0/40 = 0%** (Wilson [0%, 8.8%]) vs **+validation 18/40 = 45%** ([30.7%, 60.2%]),
gap **+45.0 pp, Newcombe [+28.2, +60.2]** — clears 0, non-overlapping bars, a **real** result. Validation fired
20 times; 17 of the 18 wins were genuine fired-and-corrected runs (`100.0` → re-prompt → `158`).

**The novel part — the residual, decomposed.** The 55% that validation did *not* recover is the guardrail's
disclosed blind spot, now **measured** by hand-reading every miss:

| Slice | Share | Why validation can't touch it |
| --- | --- | --- |
| never retrieved the rate | 35% (14/40) | nothing to recompute from — the validator **accepts by design** rather than guess |
| wrong-record retrieval | 10% (4/40) | fetched the *wrong zone's* rate (`12`), submitted `152` = `140+12` — perfectly self-consistent, so the validator **accepts it** (the oracle still fails it) |
| non-numeric submission | 7.5% (3/40) | a formula string can't be compared to a number; passed through, oracle fails it |
| never submitted | 2.5% (1/40) | nothing submitted, nothing to validate |

That 10% row is the exact fooling scenario D22 could only *describe* — S10 caught it happening, four times.
(One nuance we disclose: the validator anchors on the *first* retrieved value of each field, so a run that
fetched `12` first and `18` later was still checked against the wrong-evidence total.)

**Teaching note.** The keeper idea: **a guardrail's honest limit is part of the measurement.** S9's 100% and
S10's 45% are the *same guardrail* — what changed is the failure mix it was pointed at. On clean slips
(right evidence, wrong sum) it recovers everything; on a messy hallucination gap it recovers exactly the
self-consistency-violating slice and is structurally blind to the rest. Together the two stages bracket the
mechanism: validation fixes *consistency* failures, never *evidence* failures — and the honest deliverable
isn't "45%", it's "45% recovered, and here is precisely what the other 55% is." A deployer reading only S9
would over-trust the check; S10 is the number that calibrates it.

**New words.** *hallucinated answer*, *un-validatable slice*, *gap decomposition*, *un-stacked ablation*,
*accept-by-design*, *first-evidence anchoring*.

**Recall — try before you reveal:**

Q1. S9 measured this same guardrail at 100%; S10 measured it at 45%. What actually changed — and why is 45%
the *more* useful number for someone deploying a validation check?

<details><summary>answer</summary>

The guardrail didn't change — the *failure mix* did. nemo's misses were all arithmetic slips on correctly-retrieved evidence, the one failure a self-consistency check catches perfectly, so S9 was its best case. llama's misses are mostly *evidence* failures — 35% never fetched the rate, 10% fetched the wrong record, 7.5% submitted non-numbers — which a check that recomputes *from the model's own evidence* structurally cannot see. 45% is the more useful number because it tells a deployer what validation actually is: a consistency checker that recovers one slice of a messy gap, not a fix-all — and the hand-read decomposition tells them exactly which slice.

</details>

Q2. One llama run fetched the wrong zone's shipping rate (`12`), and validation *accepted* its `152`. Why is
accepting it the **correct** behaviour for this guardrail — and what would it cost to "fix" it?

<details><summary>answer</summary>

Because `152` *is* self-consistent: `140 + 12` matches the evidence the model gathered this run, and the run's own evidence is all the validator is allowed to read. To reject `152` the validator would need to know the *true* rate is `18` — i.e., read the canonical records — which turns the self-consistency check into a smuggled answer key. That would force 100%, destroy the honesty of the measurement, and be undeployable (at run time in the real world you don't *have* the answer key). The blind spot is the price of not cheating; S10's contribution is measuring its size (10% of this model's gap) instead of just disclosing it exists. The oracle, which *does* read the canonical records, still fails the run — grading and guarding stay separate.

</details>

Q3. The first N=40 run crashed at trial 13. What was the root cause, and why did the fix route non-object
arguments through the *existing* malformed-arguments path instead of trying to make the call work?

<details><summary>answer</summary>

Root cause: the code treated "the arguments string parsed as JSON" as "the arguments are usable" — but llama sometimes emits a JSON *array*, which parses fine yet isn't the name→value object a function call needs, so `args.get("value")` blew up on a list. The fix is one check — parsed arguments must actually be an object (`isinstance(args, dict)`) — and anything else takes the same path as unparseable JSON: the tool is not run, and the model observes an honest "malformed arguments" error. Routing through the existing path matters for measurement integrity: if the harness instead guessed what the model meant (e.g. mapped the array onto parameters), it would be silently *helping* the model — an unmeasured guardrail contaminating the baseline. The model's malformed call stays the model's failure; it just no longer crashes ours.

</details>

---

## S11 — Declared done: the capstone ladder, and why stopping is a result too

**What we built.** Nothing that calls a model. S11 (DECISIONS D24) freezes scope and makes the finished
story legible: one **capstone figure** (`docs/figures/capstone-ladder.png`) that reads the whole project as
a **capability ladder** — the same clean task across three models from strong to weak, baseline vs
+matched-guardrails — plus README §12 (the whole story on one page) and this spine close-out. The other
two candidate directions (a live capability-ladder sweep across more models; a genuinely self-hosted
endpoint) were weighed and recorded in D24 as *new projects*, not pending stages.

**How the figure stays honest (the part worth defending).** Three design calls carry the integrity:

- **GLM-4.6 gets no guardrail bar.** No guardrail arm was ever *run* on its clean task — four probes showed
  there was nothing to close — so a second 100% bar would plot a measurement that doesn't exist. An
  annotation states the finding instead, and the caption notes GLM's +32.5 pp win lived on the *injected*
  testbed.
- **nemo's +100 pp gap is a disclosed cross-run comparison.** Its 0/20 baseline is the S8 run; its 40/40
  stack is the S9 run. Two independent proportions make a valid Newcombe interval ([+81.7, +100.0]), but the
  pair is *not* one paired ablation — so the caption says "CROSS-RUN" rather than letting it read as one.
- **The data file is derived, never hand-typed.** `chart.py` rebuilds `capstone-data.json` from the vendored
  per-stage JSONs on every run (recomputing the cross-run gap via `stats.py`), and a test pins the committed
  file to a fresh derivation — so the summary figure *cannot* silently drift from the per-stage figures it
  summarizes. The single hand-typed number (S3's 20/20, which predates the vendoring convention) is a
  documented constant.

**Teaching note.** The keeper idea: **declaring done is a measured decision, not a fade-out.** The evidence
that S11 was the right stage to stop: the thesis closed at S9 (every failure class has its matched guardrail,
each under the CI gate), and S10 *bracketed* the last mechanism (best case 100%, messy case 45% + a
quantified blind spot). Bracketed at both ends means more bars would add breadth, not understanding — and a
capstone that inherits every per-stage honesty rule (verdict colouring, disclosed provenance, the non-bar)
is worth more to a reader than another ablation. Stopping with evidence is the same skill as pivoting with
evidence (S3's kill-trigger, S7's stop rule) — pre-committed criteria, honestly applied.

**New words.** *capstone figure*, *capability ladder*, *cross-run comparison*, *derived data file*.

**Recall — try before you reveal:**

Q1. The capstone shows GLM-4.6 with only ONE bar. Why — and what exactly would be dishonest about adding a
second 100% bar labelled "+guardrails"?

<details><summary>answer</summary>

Because no guardrail arm was ever run on GLM's clean task. S3/S6/S7 showed the baseline was already at ceiling (20/20 clean, self-heals malformed calls, 8/8 twice on hardened tasks), so there was no gap for a guardrail to close and the arm was never spent. A "+guardrails 100%" bar would therefore plot a *measurement that doesn't exist* — a reader would take it as "we ran guardrails on GLM and they held at 100%," which we never did. The honest move is the annotation ("no natural gap — nothing to close") and a caption note that GLM's real guardrail win (+32.5 pp) was on the *injected* testbed — a different chart, saying so.

</details>

Q2. nemo's +100 pp gap on the capstone is flagged "CROSS-RUN." What does that mean, why is the statistic
still valid, and why must the caption disclose it anyway?

<details><summary>answer</summary>

The two bars come from two different experiments: the 0/20 baseline was measured in S8, and the 40/40 submit-nudge+validation stack in S9. The Newcombe interval is still valid because it only assumes two *independent* proportions — which two separate runs are. But every other gap in the project comes from a *paired* ablation (both arms over the same trials in one run), so without the flag a reader would assume this one does too. Disclosure keeps the figure's claims exactly as strong as the data — the house rule that a chart must never read better than what was measured.

</details>

Q3. `capstone-data.json` is rebuilt from the per-stage JSONs every time `chart.py` runs. What failure mode
does that *derived* design prevent, and what's the one hand-typed number in the ladder?

<details><summary>answer</summary>

It prevents **drift**: if the summary's numbers were typed by hand, a later correction to a per-stage figure (or a transcription typo) could leave the capstone quietly disagreeing with the figures it claims to summarize — the worst kind of error in a deliverable, because nothing would flag it. Deriving at render time (plus the test that the committed file equals a fresh derivation) makes disagreement impossible. The one hand-typed number is GLM's 20/20 from S3, which predates the vendored-summary convention — carried as a documented constant in `chart.py` and disclosed in D24.

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
- **retry-nudge** — the S6 guardrail: re-prompt the *model* to fix and retry a failed call — which costs it a turn (vs error-recovery's no-turn harness retry). Built as the `nudge` toggle in `agent.py`. Against malformed calls on GLM-4.6 it measured a *null* — the model self-corrects unaided.
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
- **malformed call** — a tool call that is itself wrong (wrong parameter name/type, bad JSON), so the tool rejects it — as opposed to a *transient* fault, where the call is fine but the service hiccups. The S6 fault (`with_malformed_faults`).
- **sticky fault** — a fault that recurs on an *identical* re-call, so only a genuinely *changed* call clears it (the malformed fault), versus a fresh per-call coin-flip (the 503) that any resend can clear.
- **permanent / non-retryable error** — an error a blind retry can't fix (a malformed call, an unknown id); `agent._is_retryable` returns False for it, so error-recovery leaves it alone. Opposite of a transient error.
- **self-correction** — the model fixing its own failed call after reading the tool's error (e.g. switching `order_id` → `id`), with no guardrail — the behaviour that made retry-nudge measure null on GLM-4.6.
- **null result** — a measured difference whose confidence interval straddles 0, so you can't claim an effect; reported honestly as "no clear effect," never a win (the honesty gate).
- **guardrail specificity** — each guardrail fixes its own failure type and not others (error-recovery↔transient turn-exhaustion, retry-nudge↔malformed) — and a guardrail helps only where the model can't self-correct.
- **N-arm ablation** — running *N* arms (not just two) over one shared fault, each with a Wilson CI and a Newcombe gap vs the baseline (`ablation.run_arms`); generalises the S4 two-arm harness at the seam.
- **pilot run** — a tiny, cheap trial run done first to de-risk a bigger, costlier one (the N=6 pilot that caught the S6 null before the full run).
- **natural gap** — a model failing on a *clean* task (no injected faults) because the task is genuinely hard, as opposed to the *injected* gaps of S3–S6. S7 hunted one on GLM-4.6 and found none.
- **validation gap / guardrail** — a *validation gap* is a failure where the model submits a *wrong answer with no error* (wrong record/field, a dropped term); a *validation guardrail* checks the answer's consistency before accepting it. Neither error-recovery nor retry-nudge (which fire only on tool *errors*) nor submit-nudge (a *missing* call) can close a validation gap. **Built in S9** (the `validate` toggle) and measured at **+25 pp** on mistral-nemo's arithmetic-slip residual.
- **failure triage** — hand-reading a run's trajectory to classify *why* it failed (transient error / malformed call / wrong-answer-no-error / no-submit / max-steps), not just that it did.
- **bounded escalation** — a pre-committed rule allowing task difficulty to be raised only a fixed number of times, with a hard stop (S7: escalate once; if GLM still scores ≥7/8, declare done) — so a gap hunt can't become an open-ended chase.
- **at ceiling** — scoring at (or statistically indistinguishable from) 100%, leaving no room to measure an improvement; GLM-4.6 is at ceiling on both the clean and the hardened tasks.
- **robustness signal** — an independent observation that a model handles a task class without help; S7 collected four (20/20 clean, self-heals malformed, 8/8 hard-v1, 8/8 hard-v2).
- **submit-nudge** — the S8 guardrail: when a run ends in prose with nothing submitted, re-prompt the *model* to actually call the terminal tool, then continue (the `submit_nudge` toggle in `agent.py`). The natural-failure counterpart to retry-nudge — it fires on a *missing* terminal call, not a *failed* one.
- **protocol gap / no-submit** — a failure where the model has the right answer but doesn't follow the interaction *protocol*: here, never emitting the `submit_answer` tool call (it narrates the answer as prose and stops). mistral-nemo's natural failure; what submit-nudge closes.
- **capability cliff** — a task where models cluster at the extremes — strong ones *ace* it (no gap), weak ones *fail wholesale* (≈0%) — with a narrow or empty "fails a little, mechanically" band between. Both S8 weak models landed at 0%, by different failure modes.
- **bifurcation** — when a probe splits into two qualitatively different outcomes rather than a tidy middle (here, two weak models failing 0% in two *different* ways: hallucinated answer vs no-submit); the signal that triggered S8's pivot.
- **fit pilot** — a tiny baseline-only run used to check whether a candidate model lands in the measurable "sweet spot" (not ~100%, not ~0%) *before* committing to a full ablation — model-selection's version of the S6/S7 pilot.
- **capability × guardrail interaction** — the S8 thesis: how much a guardrail helps depends on the *model's* capability — a submit-nudge is worthless on GLM-4.6 (it always submits) but worth +75 pp on mistral-nemo (which forgets to). The claim is the interaction, not "model X is bad."
- **self-consistency check** — validating an answer against the evidence the model *itself* gathered this run (its own tool results), **not** against the grader's ground truth. The S9 guardrail: it recomputes the total from the retrieved data, so it catches "had the pieces, summed wrong" but can be fooled by a wrong-record retrieval — a principled blind spot that keeps it from being a smuggled answer key.
- **stacked ablation** — an ablation whose reference arm already has one guardrail switched on (here submit-nudge), so a *second* guardrail (validation) is measured *on top* of it. Used when the lower guardrail is what makes the higher one's failure visible at all (you can't measure "submits the right number" until you've got it to submit).
- **scaffolding** — a guardrail whose role in an experiment is to *expose* the failure another guardrail targets, by clearing the failure that was masking it (submit-nudge is scaffolding for the S9 validation measurement: 0% → 75% first, so the wrong-answer residual becomes measurable).
- **hallucinated answer** — a submitted value grounded in nothing the model retrieved (llama-8b's `1234.56`, or the literal formula string `"item_total_usd + ship_rate"`); the messy wrong-answer failure S10 pointed validation at.
- **un-validatable slice** — the fraction of a wrong-answer gap a self-consistency check structurally cannot catch: missing evidence (nothing to recompute from), wrong-record retrieval (a self-consistent wrong total), or a non-numeric submission. S10 measured it at 55% of llama-8b's gap.
- **gap decomposition** — hand-reading every miss and splitting a measured gap into labelled failure slices with shares (S10: 35% never-retrieved · 10% wrong-record · 7.5% non-numeric · 2.5% no-submit), so the residual is *explained*, not just reported.
- **un-stacked ablation** — an ablation whose reference arm is the bare baseline again (contrast *stacked*): possible in S10 because llama-8b submits unaided, so no lower guardrail is needed to expose the wrong-answer failure.
- **accept-by-design** — the validator's rule when it *cannot* recompute (evidence missing or the submission non-numeric): accept rather than guess. Prevents false rejections, and is exactly what makes the un-validatable slice measurable instead of hidden.
- **first-evidence anchoring** — the validator recomputes from the *first* retrieved value of each field, so a run that fetched the wrong rate first (and the right one later) is still checked against the wrong-evidence total. A disclosed design property of `scenario.validate`, observed once in S10.
- **incremental (marginal) lift** — the extra completion a guardrail adds *over the arm below it*, not over the bare baseline. S9 reports validation's incremental lift over submit-nudge (75% → 100% = +25 pp), which isolates validation's own contribution from submit-nudge's.
- **capstone figure** — the single summary chart a finished project leads with; here the S11 capability ladder, which re-plots only already-measured numbers under every per-stage honesty rule.
- **capability ladder** — the same task across models of increasing weakness, showing how the natural gap opens up and how much of it a matched guardrail closes at each rung (GLM: no gap → nemo: fully closed → llama: 45%, blind spot bounded).
- **cross-run comparison** — a gap computed between arms measured in two *different* experiments (nemo's S8 baseline vs its S9 stack). Statistically valid for independent proportions, but not a *paired* ablation — so it's disclosed on the figure rather than left to read as one.
- **derived data file** — a vendored JSON built automatically from other vendored JSONs at render time rather than typed by hand (`capstone-data.json`), so a summary can never silently drift from its sources; pinned by a test that the committed file equals a fresh derivation.
