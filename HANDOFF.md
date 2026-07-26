# HANDOFF.md

_Last updated: 2026-07-26_

## What was just done
- Project wiki initialized (PROJECT.md, HANDOFF.md, Sources.md + CLAUDE.md wiring) — this commit.
- Last substantive work (2026-07-17, merge 5b51c3c / PR #23): vendored global Claude Code tooling into `.claude/` via `/claudify-repo`.
- Before that: repo hygiene (PR #20 — CI workflow, `uv run pytest` entry point, MIT license) and the dated whole-project guide (PR #19, `docs/project-guide/2026-07-06-forge-gap-guide.md`).

## Where things stand
The project is **COMPLETE — declared done at S11 (D24, 2026-07-06)**. All twelve stages (S0–S11) shipped; every guardrail is measured, every figure is committed with vendored data, and the capstone capability-ladder figure + README §12 tell the whole story. `main` is clean and up to date with `origin/main` (github.com/ksdisch/forge-gap, public). All 77 offline tests pass via `uv run pytest`; CI runs them on every PR.

## Immediate next move
None in this repo — it is closed on purpose. Successor research-repro projects continue the lineage elsewhere. If work here ever resumes, the required first step is a **new decision brief** for one of the D24 roads not taken (live ladder sweep or self-hosted endpoint) — not new experiment code (Decision: docs/DECISIONS.md D24).

## Open questions / blockers
- None blocking. (The validator's 55% blind spot on llama-8b is a *measured, disclosed* limitation, not an open task — D23.)

## Files touched recently
- `.claude/` (commands, skills, session-start.md, operating-constraints.md) — vendored tooling, PR #23
- `CLAUDE.md` — tooling reference section (PR #23), pytest line (PR #21), wiki wiring (this commit)
- `.github/`, `pyproject.toml`, `LICENSE` — repo hygiene, PR #20
- `PROJECT.md`, `HANDOFF.md`, `Sources.md` — wiki init, this commit
