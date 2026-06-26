# forge-gap — S2: lookup-then-compute scenario + deterministic oracle
**Date:** 2026-06-26 · **Branch merged:** `feat/s2-scenario-oracle` → `main` (`ec3472c`) · **PR:** #1 · **Feature commit:** `19e0573`

> Project context for a cold reader: **forge-gap** is a small harness that *reproduces and measures* reliability guardrails for a cheap open model (GLM-4.6, via OpenRouter) on a multi-step tool-use task. The end deliverable is a "gap-closure chart": how much each guardrail (retry-nudge, error-recovery) lifts task-completion over a no-mechanism baseline, with proper confidence intervals. It's built in phases S1→S12. S1 shipped the bare agent loop; **today was S2**.

---

## 1. What we did
- Built `scenario.py` — the "order grand total" task as a frozen `Scenario` dataclass: two **chained** tools (`get_order` → `get_ship_rate`) + a `submit_answer` terminal tool; ground truth `140 + 18 = 158` computed in plain Python from fixed records.
- Built `oracle.py` — a pure `grade(submitted, expected)` deterministic grader; coerces/validates the submitted value and maps missing/malformed/non-numeric answers to a `no_numeric_answer` failure. **No model call.**
- Generalized `agent.py` — the S1 reason→act→observe loop now drives *any* `Scenario`: `dispatch(name, args, registry)`, a terminal-tool intercept, a `submitted | no_submit | max_steps` stop taxonomy, and a new `grade` trajectory event. The original loop + its 3 mechanical-failure phases are preserved.
- Added `test_oracle.py` — 18 offline checks (no network, no pytest) over the oracle, ground-truth consistency, and `dispatch`.
- Updated docs — `README.md` (run section + file tree), `CLAUDE.md` (file map).
- Verified end-to-end: `test_oracle.py` **18/18**; one real GLM-4.6 run graded **PASS** (`submitted=158 == expected=158`, 3 reasoning turns, 11 trajectory records).
- Two decisions resolved with the user via clarifying questions: scenario domain (**order + shipping, chained**) and answer capture (**`submit_answer` tool**).

---

## 2. The why
- **Chained lookup + *trivial* arithmetic (together).** The chain forces the agent to thread `ship_zone` out of call 1 into call 2 — exactly where multi-step agents fail *mechanically* (wrong field, wrong arg, skipped step). Trivial math keeps failures from being *cognitive*. Rejected alternatives: two independent balances + a sum (too easy → risks no gap to measure) and salary-÷-budget (its difficulty is arithmetic → manufactures *cognitive* failures, the wrong kind). **Principle:** design the measurement so variance lands on the variable you're isolating.
- **`submit_answer` terminal tool over prose-parsing.** A structured numeric arg → exact grading, zero text parsing. Rejected: regex-a-number-out-of-the-sentence (fragile; a *formatting* miss looks identical to a *compute* error, weakening the oracle). Tradeoff accepted: the loop's terminal condition changes from "no tool call" to "submit_answer called" — which is actually a cleaner completion signal. **Principle:** structured output at the boundary you grade > parsing free text.
- **Deterministic oracle, never an LLM judge.** Ground truth is computed by a *separate* Python path over the same records, so the agent never scores itself (no circularity); grading is reproducible equality. An LLM judge is "self-graded homework": correlated blind spots, sycophancy, run-to-run drift — noise injected into the ruler. **Principle:** use a fixed ruler to measure a small delta.
- **Module split: `scenario.py` (task-as-data) / `oracle.py` (grader) / `agent.py` (engine).** The `Scenario` bundle is the stable boundary that S4's ablation runner will vary mechanism-arms across (mechanisms wrap the *loop*, the *task* stays fixed). Rejected: keep it hardcoded in `agent.py`. **Principle:** introduce the parameter object at the natural seam — and only there (the old `agent.py` docstring literally anticipated this swap, so it isn't premature).
- **Stop taxonomy + `grade` event.** `submitted` / `no_submit` / `max_steps` distinguishes "submitted the wrong number" from "never submitted" from "ran out of steps." **Principle:** log the failure *mode*, not just pass/fail — that's the input to S3's triage.

---

## 3. Concepts and vocabulary
- **Reason→act→observe loop** *(a.k.a. agent loop / ReAct-style)* — model picks a tool, tool runs, result is fed back, repeat. → `agent.py:run()`.
- **Function calling / tool schema** — OpenAI-format JSON describing a callable; the model emits structured `tool_calls`. → the `*_TOOL` dicts in `scenario.py`.
- **Chained / dependent tool calls** — call 2's arguments come from call 1's result. → `get_ship_rate(zone)` where `zone` came out of `get_order`.
- **Terminal tool / structured final answer** *(final-answer tool)* — a tool whose call ends the run and carries the answer. → `submit_answer` intercept in `agent.py`.
- **Deterministic oracle** — grader that compares output to known ground truth by fixed rule, no model. → `oracle.py:grade()`.
- **LLM-as-judge** *(the "self-graded homework" trap)* — using a model to grade model output; deliberately rejected here. → the teaching note in chat.
- **Mechanical vs cognitive failure** — the *machinery* of a step broke (malformed call, wrong record, no convergence) vs the model couldn't *reason* it out. → `agent.py` docstring's 3 phases; the whole scenario design.
- **Ground truth** — the known-correct answer, computed independently. → `scenario.py:GROUND_TRUTH` (140+18=158).
- **Trajectory (JSONL log)** — one structured event per line for hand-reading a run. → `trajectory.jsonl`; events `run/reason/act/observe/final/grade`.
- **Frozen dataclass as parameter object** — immutable bundle passed in lieu of many loose args. → `Scenario` in `scenario.py`.

---

## 4. Takeaways
- **Design the task so the failure you want to study is where failures actually land.** Today: chained lookup + trivial math → failures are mechanical (the kind S3 needs), not arithmetic. Generalizes to any experiment: strip confounds so variance comes from your variable.
- **Structured output beats parsing prose when you need an exact grade.** Today: `submit_answer(value)` instead of regex-on-a-sentence. Anywhere you grade model output, make it emit machine-readable results at that boundary.
- **Never let your measuring instrument add noise correlated with what you're measuring.** Today: deterministic oracle, not an LLM judge, because the deliverable is a small completion-rate *delta* with CIs.
- **Parameterize at the natural seam, not before it.** Today: the `Scenario` bundle appears exactly when a second use (the coming ablation runner) makes the seam obvious — that's the line between "good abstraction" and "premature abstraction."

---

## 5. Suggested next moves
1. **(Recommended) S3 — the gap diagnostic + John checkpoint.** Run this scenario at **N≈20** on GLM-4.6 *and* a frontier model; hand-read trajectories to prove (a) a real gap exists and (b) failures are *mechanical*, not cognitive. *Why first:* it's the thesis hinge and **gates every mechanism in the project** — you don't build a guardrail until you've proven there's a recoverable gap to close. *Effort:* medium — needs a small N-trial runner, a frontier-model arm, and manual triage. *Heads-up:* today's single run passed first try with the steps spelled out, so S3 may show GLM ≳85% (kill-trigger 1) → then tune the scenario harder or inject faults, and say so plainly.
2. **Update the hub `ACTIVE-PLAN.md`** to mark S2 shipped → focus S3 (the S1 session did this). *Effort:* tiny. *Note:* it's the sensitive hub repo — left untouched today pending a nod.
3. **Harden `verify.py`'s plain-chat check.** It soft-failed today because GLM-4.6 returned empty `content` (20 completion tokens, no text) and the check naively does `bool(text)`. *Effort:* trivial (~2 lines). *Priority:* low — cosmetic, not blocking; pre-existing, unrelated to today's code.

---

## 6. 30-second elevator version
forge-gap measures how much reliability tricks actually help a cheaper open model — GLM-4.6 — get through a multi-step tool task. Today I built the task it measures and the grader. The task is a two-step lookup-then-compute: the agent looks up an order, looks up the shipping rate for that order's zone, adds them, and submits the total. The grader is deliberately dumb-but-honest — it compares the submitted number to a known answer computed in plain Python, never one model judging another, because I'm trying to detect a small completion-rate difference and a model-judge would add noise to the ruler itself. The design call I'd highlight is making it a *chained* lookup with *trivial* math, so when the agent fails it fails mechanically — threading data between calls — which is the failure type the next phase has to study, not arithmetic slips. It's wired into a reason-act-observe loop with a structured JSONL trace, and one real run passed end to end.

---

## 7. Active recall
1. Walk me through what happens, step by step, when the agent runs the order scenario — from prompt to graded result.
2. Why a deterministic oracle instead of an LLM judge? What *specifically* goes wrong with the judge here?
3. You made the task a chained lookup *and* gave it trivial arithmetic. Why those two choices together?
4. Why add a `submit_answer` tool instead of parsing the number out of the model's final sentence?
5. What would you lose if you'd kept the scenario hardcoded in `agent.py` instead of extracting a `Scenario` object?

---
*Try to answer each aloud before scrolling. Answer key below.*

### Answer key
1. Build `messages` (system + task) → loop calls `chat()` with the three tool schemas → GLM emits `get_order("ORD-204")` → `dispatch` runs it, returns JSON `{item_total 140, ship_zone WEST}`, threaded back as a tool observation → GLM emits `get_ship_rate("WEST")` (**chained** — zone came from the prior observation) → returns `{rate 18}` → GLM computes 140+18 and calls `submit_answer(158)` → the loop **intercepts the terminal tool**, captures 158, stops with `stop="submitted"` → `oracle.grade(158, 158)` → `correct=True` → logs `final` + `grade` events to `trajectory.jsonl` and prints **PASS**. (3 reasoning turns, 11 records.)
2. The deliverable is a completion-rate *difference* between arms with confidence intervals, so the ruler must not wobble. Ground truth is computed by a *separate* Python path → the agent can't grade itself (no circularity). An LLM judge fails three ways: **correlated blind spots** (blind where the agent is blind → rubber-stamps the same errors), **sycophancy/inconsistency** (drifts run-to-run → injects noise into the ruler), and that noise can **swamp the small delta** you're trying to detect. Use a judge only when ground truth genuinely isn't computable — here it is.
3. **Chained** forces threading the zone from call 1 into call 2 — precisely where multi-step agents fail *mechanically* (wrong field/arg, skipped step). **Trivial arithmetic** keeps the math from manufacturing *cognitive* failures. Together they concentrate the failure surface on mechanical/recoverable errors — the kind S3 must prove exist before any guardrail is justified. Hard math would muddy the mechanical-vs-cognitive triage.
4. `submit_answer` gives a structured numeric arg → exact grading with zero text parsing. Parsing prose is fragile (`$1,580`, `1.58k`, `158.00`, multiple numbers in a sentence), and a formatting miss looks identical to a wrong computation — that ambiguity weakens the oracle and muddies triage. The cost is that the loop's terminal condition changes from "no tool call" to "`submit_answer` called" — which is actually a *cleaner*, more measurable completion signal.
5. Functionally nothing today — but you'd pay in S4. The ablation runner has to push the *same* task through the loop under different mechanism arms (retry-nudge, error-recovery); the `Scenario` bundle is the stable boundary (mechanisms wrap the *loop*, the *task* stays fixed). Hardcoded, you'd duplicate the loop per scenario or thread six loose args everywhere. The frozen dataclass is the parameter object at the natural seam — and `agent.py`'s own docstring anticipated the swap, so it isn't premature abstraction.
