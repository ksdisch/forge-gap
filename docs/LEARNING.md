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
- **proportion / confidence interval** — success is a fraction of N runs; a CI is the honest range the true rate likely sits in (we'll use Wilson + Newcombe). *(arrives with S4)*
- **ablation** — turning one factor on/off (here, a guardrail) to measure its specific effect. *(arrives with S4)*
