# CLAUDE.md — forge-gap

Project conventions and guardrails for working in this repo. Read this first each session.

## What this is
A small harness that **reproduces and measures** reliability guardrails for a self-hosted
model (GLM-4.6 via OpenRouter) on a multi-step tool-use task. The deliverable is a
**gap-closure chart**: how much each guardrail (retry-nudge, error-recovery) raises task
completion over a no-mechanism baseline, measured with proper confidence intervals.

The honest framing, always: *reproduced and measured a published primitive — here is the
narrow, measured delta.* Never "I invented this." If a gap is manufactured by injecting
faults rather than found naturally, say so plainly in the README and writeup.

## How to run
- Setup: put a real `OPENROUTER_API_KEY` in `.env` (gitignored). See `README.md`.
- Smoke test: `uv run verify.py` — exercises plain chat + one tool-calling round-trip.
- Anything else: `uv run <script>` — `uv` manages the venv and installs deps on first run.
- `uv` (Python 3.11+) is the toolchain. This is an application, not a package (`package = false`).

## File map
- `glm.py` — the minimal GLM-via-OpenRouter client (`chat()`, `MODEL`). The foundation
  everything builds on. Forwards `tools` / `tool_choice` / `temperature` straight through.
- `agent.py` — the scenario-agnostic reason→act→observe loop + deterministic grading. ZERO
  mechanisms (the bare baseline). Pure `dispatch()`; per-step JSONL trajectory plus a `grade` event.
- `scenario.py` — the S2 lookup-then-compute task as data: a frozen `Scenario` (two chained
  lookup tools + a `submit_answer` terminal tool + known ground truth).
- `oracle.py` — the deterministic grader (`grade()`): computed value vs known ground truth,
  never an LLM judge. Pure and unit-tested.
- `verify.py` — smoke test proving chat + tool-calling work.
- `test_oracle.py` — offline unit tests for the oracle, scenario ground truth, and `dispatch`.
- `check_docs.py` — freshness check for the learning spine: flags any done stage missing from
  `docs/LEARNING.md`. Run `uv run check_docs.py`. A smoke alarm, not a commit gate.
- `.env.example` — config template (committed). `.env` holds the real key (gitignored).
- `docs/` — the **learning spine**: `ROADMAP.md` (where we are), `DECISIONS.md` (what we chose &
  why), `LEARNING.md` (plain-English walk-through + glossary + recall), plus `session-logs/` (raw
  `/wrap` recaps). Start here to catch up; see `docs/README.md`.
- *(planned)* the N-trial ablation runner and the gap-closure chart.

## Methodology guardrails (load-bearing — do not drift)
- **Deterministic oracle, never an LLM judge.** Task success is measured against known
  ground truth (a computed value vs the correct answer), not a model's opinion.
- **Wilson proportion confidence intervals**, not ±std — plus a Newcombe CI on the
  difference between arms. Completion rate is a proportion; treat it like one.
- **N ≥ 20 per arm**, scaling toward ~50 if deltas are small. The binding constraint on this
  project is the **statistics (noise floor), not the code.**
- **A bar whose CI overlaps its neighbor is not a result** — report it as a null/small effect,
  honestly. Do not present overlapping CIs as a win.
- **Build the ugliest end-to-end version first**, then layer mechanisms one at a time. Prove a
  gap exists and that failures are *mechanical/recoverable* (malformed call, wrong record, 404)
  before building any guardrail to recover from them.
- Record GLM `temperature` (don't chase determinism via temp 0 — GLM is non-deterministic
  regardless; get signal from N).

## Working with Kyle — teaching standard + per-stage rhythm (load-bearing)
Kyle is driving this project to learn it deeply (it may become his career) and is sharp but
**new to coding jargon** — no CS degree. The job isn't just to ship code; it's to leave him able
to *defend every decision*. These rules bind **every session and tab**.

- **Explain-clearly standard.** Plain English first; define **every** jargon term the first time
  it appears, inline; **clearer, not longer** (the simplest accurate explanation, not the most
  exhaustive). If something stays fuzzy, that's a bug in the explanation — fix it.
- **Decision-brief format.** For any real choice, don't just pick — lay out 2–3 options in plain
  terms, each with its trade-off, plus your recommendation *and the reason*. Kyle decides or signs
  off; clear options are what make weighing in possible.
- **Per-stage rhythm (update the spine in `docs/`).** *Start of a stage:* write the plain-terms
  brief + the real options into `docs/` before coding. *End of a stage:* update `ROADMAP.md`
  (status), append the choice to `DECISIONS.md` (options + why), add the teaching note + new words
  to `LEARNING.md`, and ask 3 recall questions. The raw blow-by-blow still goes to
  `docs/session-logs/` via `/wrap`; the three curated docs are the distilled version
  (see `docs/README.md`).
- **Definition of done (keeps the spine fresh).** A stage isn't finished until its spine updates
  are committed in the **same PR** as the code, and `uv run check_docs.py` passes (it verifies
  every done stage is written up). If a session ends before that, the next `/begin` catches the
  spine up first.

## Working conventions
- **Teach while building.** After non-trivial code, explain what/why in plain English and define
  any jargon — see **"Working with Kyle"** above for the full standard + per-stage rhythm. The
  goal is code the author can defend line by line.
- **Keep it lean.** No premature abstractions, no mechanisms before the baseline reads
  honestly. Scope is one legible deliverable, not breadth.
- **Secrets:** never print or commit the `.env` value; only `.env.example` is tracked.
