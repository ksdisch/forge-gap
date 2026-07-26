# PROJECT.md

## Purpose
Reproduce and **measure** how much matched reliability guardrails (error-recovery, retry-nudge, submit-nudge, validation) raise an LLM's completion rate on a multi-step tool-use task — ending in honest gap-closure figures with Wilson/Newcombe confidence intervals (Fact: README.md, docs/ROADMAP.md).

## Scope
**In scope (all shipped):** stages S0–S11 — GLM-via-OpenRouter client, bare agent loop, lookup-then-compute scenario + deterministic oracle, fault injectors, N-trial ablation harness with CIs, four guardrails each matched to one failure class, per-stage figures, and the S11 capstone capability-ladder figure (Fact: docs/ROADMAP.md).

**Out / deferred / never (D24 "roads not taken"):** a live capability-ladder sweep across more models, and a genuinely self-hosted local-model endpoint. Either is a **new project decision**, not a pending stage — open a fresh decision brief before writing any experiment code (Decision: docs/DECISIONS.md D24).

## Current status
**Complete** — declared done at S11 (D24) on 2026-07-06. The matched-guardrail thesis is bracketed at both ends: GLM-4.6 needs no guardrails (no natural gap, four probes), and llama-8b's messy gap is only partly recoverable (+45 pp; 55% residual = the validator's measured blind spot). Post-close hygiene landed through 2026-07-17 (CI, pytest entry point, MIT license, vendored Claude tooling).

Headline measured results (Fact: README.md §12 table):
- Transient 503 → error-recovery: **+32.5 pp** [+17.3, +48.0] (GLM-4.6, injected, S4)
- Malformed call → retry-nudge: **null** — GLM self-heals (S6)
- No-submit → submit-nudge: **+75 pp** [+47.8, +88.8] (mistral-nemo, natural, S8)
- Wrong-answer → validation: **+25 pp** [+11.1, +40.2] (nemo, S9) and **+45 pp** [+28.2, +60.2] (llama-8b, S10)

## Next actions
1. None pending — the project is closed on purpose (Decision: D24).
2. If ever revived: start from a new decision brief for one of the D24 roads not taken; do not add stages to this repo without one.

## Boundaries
- **Toolchain:** `uv` (Python 3.11+); application, not a package. Tests: `uv run pytest` (77 offline tests, no API key; CI runs on every PR).
- **API access:** live runs need `OPENROUTER_API_KEY` in `.env` (gitignored); all figures regenerate offline from vendored `docs/figures/*-data.json` via `uv run chart.py`.
- **Methodology (load-bearing, from CLAUDE.md):** deterministic oracle (never an LLM judge); Wilson + Newcombe CIs; N ≥ 20 per arm; a CI that straddles zero is reported as a null, never a win; injected gaps are always disclosed as injected.
- **Docs spine:** `docs/ROADMAP.md` / `docs/DECISIONS.md` / `docs/LEARNING.md` are the authoritative in-repo record; this wiki layer points at them rather than duplicating them (see Sources.md).
