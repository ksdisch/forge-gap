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
- `.env.example` — config template (committed). `.env` holds the real key (gitignored).
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

## Working conventions
- **Teach while building.** After non-trivial code, explain what/why in plain English and
  define any jargon. The goal is code the author can defend line by line.
- **Keep it lean.** No premature abstractions, no mechanisms before the baseline reads
  honestly. Scope is one legible deliverable, not breadth.
- **Secrets:** never print or commit the `.env` value; only `.env.example` is tracked.
