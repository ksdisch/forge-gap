# Experiment-Harness

## Purpose
A map of how the code is actually organized to run an experiment: entry points, the
guardrail toggle system, what a "run" produces, and where results land. For anyone
who wants to reproduce a measurement, add a new arm, or understand what each script does
without reading every file.

## Key understanding

### Architecture in one sentence

**Fact** — the harness is a layered stack: `glm.py` (API client) → `agent.py` (loop +
guardrail toggles) → `scenario.py` + `oracle.py` (task + grader) → `faults.py` (optional
fault injectors) → `runner.py` (single-arm looper) → `ablation.py` (multi-arm harness) →
per-experiment scripts (entry points). `chart.py` and `stats.py` are offline post-processing;
they make no API calls. Source: [CLAUDE.md](../CLAUDE.md), "File map" section.

### The guardrail toggle system

`agent.py`'s `run()` function exposes four independent boolean toggles, each corresponding
to one measured guardrail:

| Toggle | Stage | What it does | Cost |
|---|---|---|---|
| `recover=True` | S4 | harness-level retry of transient 503s (matches `_is_retryable`) | no model turn |
| `nudge=True` | S6 | re-prompts model to correct a malformed/failed tool call | 1 model turn |
| `submit_nudge=True` | S8 | re-prompts model to call `submit_answer` if a turn ends in prose without submitting | 1 model turn |
| `validate=True` | S9 | on `submit_answer(value)`, recomputes from retrieved observations; re-prompts on mismatch | 1 model turn |

**Fact** — all four toggles default to `False`; the bare baseline runs with no mechanisms.
The toggles are additive: any combination is valid, and the S9 stacked ablation uses
`submit_nudge=True, validate=True` simultaneously. Source: [CLAUDE.md](../CLAUDE.md) `agent.py`
entry.

**Inference** — the toggle design means adding a new guardrail requires (a) one new flag on
`run()`, (b) one arm config in `ablation.py`, and (c) a new per-experiment entry-point script;
no existing mechanism code changes. This is why S6, S8, S9, S10 each reused the same harness
without rewrites.

### Arm configuration and the ablation harness

`ablation.py` defines arms as config dicts: `{"label": str, "run_kwargs": dict}`. The
harness in `run_arms()` runs each arm N times over identical seeded scenarios, computes
Wilson CIs per arm, and computes a Newcombe gap vs the designated baseline arm.

**Fact** — the five named arm configs live in `ablation.py`:
`BASELINE_ARM`, `RECOVERY_ARM`, `NUDGE_ARM`, `SUBMIT_NUDGE_ARM`, `VALIDATION_ARM`
(stacked, S9), `VALIDATION_ONLY_ARM` (un-stacked, S10). Source: [CLAUDE.md](../CLAUDE.md)
`ablation.py` entry.

Per-experiment scripts pick subsets:
- `ablation.py` (run directly): S4/S5 2-arm error-recovery ablation
- `malformed_ablation.py`: S6 3-arm malformed-call ablation
- `weak_ablation.py`: S8 3-arm submit-nudge ablation on a weak model
- `validation_ablation.py`: S9 stacked 2-arm validation ablation
- `hallucination_ablation.py`: S10 un-stacked 2-arm validation ablation on llama-8b

**Fact** — every per-experiment script accepts the model and N as command-line arguments;
fault-rate is a third argument where applicable. Source: D15 and D19,
[docs/DECISIONS.md](../docs/DECISIONS.md) ("operating point is a runtime knob").

### Fault injection and the clean-vs-injected boundary

`faults.py` provides two non-mutating injectors that wrap the base scenario:
- `with_faults(scenario, rate, seed)` — injects transient 503s at a given rate (S3–S5).
- `with_malformed_faults(scenario, rate, seed)` — injects a sticky malformed-call fault
  (S6); "sticky" means the same call keeps failing until corrected (D19).

**Fact** — `rate=0` is equivalent to the clean task for either injector; S8–S11 run on
the clean task with no injector wrapper. The fault classification boundary is encoded in
`agent._is_retryable()`: a 503/timeout → recoverable by `error-recovery`; a 400 with
`invalid_argument` → not retryable (error-recovery leaves it alone). Source: D19,
[docs/DECISIONS.md](../docs/DECISIONS.md), "Two load-bearing properties."

### Where results land

| Output | Location | Gitignored? | Notes |
|---|---|---|---|
| Per-trial trajectories | `runs/<experiment>/trial-*.jsonl` | yes (gitignored) | Full step-by-step JSONL per run; hand-read for failure triage |
| Per-experiment summary | `runs/<experiment>-summary.json` | yes | Raw k/N + CIs; input to `chart.py` |
| Vendored figure data | `docs/figures/*-data.json` | no (committed) | Copied from `runs/` after a live run; charts regenerate from these |
| Figures | `docs/figures/*.png` | no (committed) | Regenerate with `uv run chart.py` — no API, no model call |

**Fact** — the vendoring step is manual: after a live run, copy the summary JSON into
`docs/figures/` so the figure can regenerate in-repo from a clean clone. The capstone data
file (`docs/figures/capstone-data.json`) is an exception: `chart.py` derives it
automatically from the three per-stage JSONs on every run, so it can never silently drift.
Source: D18 and D24, [docs/DECISIONS.md](../docs/DECISIONS.md).

### Entry points and how to reproduce

| What to run | Command | Prerequisites |
|---|---|---|
| Smoke test (API + tool-calling) | `uv run verify.py` | `OPENROUTER_API_KEY` in `.env` |
| All offline tests (77 tests, no API) | `uv run pytest` | none |
| S4 error-recovery ablation | `uv run ablation.py z-ai/glm-4.6 40 0.6` | API key |
| S6 malformed ablation | `uv run malformed_ablation.py z-ai/glm-4.6 20 0.6` | API key |
| S7/8 pilot (hardened task) | `uv run pilot.py` or `uv run pilot.py v2` | API key |
| S8 weak-model ablation | `uv run weak_ablation.py mistralai/mistral-nemo 20` | API key |
| S9 stacked validation | `uv run validation_ablation.py mistralai/mistral-nemo 40` | API key |
| S10 hallucination ablation | `uv run hallucination_ablation.py meta-llama/llama-3.1-8b-instruct 40` | API key |
| Regenerate all figures (offline) | `uv run chart.py` | none (reads vendored JSONs) |
| Check docs freshness | `uv run check_docs.py` | none |

**Fact** — all reproduce commands sourced from D17, D19, D22, D23, D24 measured-result
sections in [docs/DECISIONS.md](../docs/DECISIONS.md) and the [CLAUDE.md](../CLAUDE.md)
"How to run" section.

### The S10 harness fix — mid-experiment disclosure

**Fact** — mid-S10, a latent bug was discovered: llama-3.1-8b sometimes emits tool-call
arguments as a JSON array (`["ORD-204"]`) rather than a dict. `agent.py` conflated "JSON
parsed" with "arguments OK," causing a crash on `.get()` applied to a list. Fix:
`args_ok = isinstance(args, dict)` — non-object args now route to the existing
malformed-arguments path. The fix adds no new help to the model; it only prevents a crash.
The pilot ran pre-fix; the full N=40 run ran post-fix. This is disclosed in D23,
[docs/DECISIONS.md](../docs/DECISIONS.md). Source: D23 "A latent harness bug, exposed
and fixed mid-stage."

## Sources
- [CLAUDE.md](../CLAUDE.md) — "File map" section (per-file descriptions)
- [docs/DECISIONS.md](../docs/DECISIONS.md) — D11 (lean runner), D14 (toggle design), D15 (operating-point knobs), D16 (ablation arms-as-config), D18 (vendoring convention), D19 (fault stickiness + `is_retryable`), D23 (S10 harness fix)
- [docs/ROADMAP.md](../docs/ROADMAP.md) — per-stage "What it does" column
- `ablation.py`, `agent.py`, `faults.py`, `chart.py` — code (entry points, toggle signatures, injector wrappers)

## Uncertainties & contradictions
- **Unresolved** — the `trajectory.jsonl` root-level file (tracked in the repo) appears to be a leftover from early development; it is not a run output from any named experiment. Its relationship to the gitignored `runs/` outputs is not documented.
- **Inference** — the `check_docs.py` freshness check is described as "a smoke alarm, not a commit gate" ([CLAUDE.md](../CLAUDE.md)); this means it is possible for the docs spine to drift without CI catching it. No evidence of such drift in the current state.

## Related pages
- [Results-Synthesis](Results-Synthesis.md)
- [Methodology-Guardrails](Methodology-Guardrails.md)
- [History](History.md)

## Relevance to current work
The project is closed; no new experiment code should be added without a decision brief
(D24). This page is the entry point for anyone resuming the project or forking the harness
for a new repro — it answers "what do I run and where do results land?" without requiring a
full code read.

_Last reviewed: 2026-07-26_
