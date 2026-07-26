# Sources

Authoritative in-repo sources. The wiki layer (PROJECT.md / HANDOFF.md) points here instead of duplicating content. Note: this project's decision log already exists as `docs/DECISIONS.md` (append-only, D1–D24) — no separate root `Decisions.md` is kept, to avoid an uncontrolled duplicate.

| Source | Location | Type | Authoritative for |
|--------|----------|------|-------------------|
| Roadmap | `docs/ROADMAP.md` | spine doc | Stage ladder S0–S11, per-stage status + measured outcomes |
| Decision log | `docs/DECISIONS.md` | spine doc (append-only) | Every decision D1–D24: options weighed and why one won |
| Learning notes | `docs/LEARNING.md` | spine doc | Plain-English walk-throughs, glossary, recall questions |
| README | `README.md` | write-up | Public narrative §1–§12 incl. the capstone story and all headline numbers |
| CLAUDE.md | `CLAUDE.md` | conventions | File map, methodology guardrails, teaching standard, project status |
| Figure data | `docs/figures/*-data.json` | vendored measurements | The exact numbers behind every committed figure; `capstone-data.json` is DERIVED — never hand-edit |
| Figures | `docs/figures/*.png` | rendered deliverables | The committed charts (regenerate via `uv run chart.py`, offline) |
| Session logs | `docs/session-logs/` | raw `/wrap` recaps | Blow-by-blow session record (S2, S8) |
| Project guides | `docs/project-guide/` | dated snapshots | Whole-project guides (2026-06-29, 2026-07-06 — the latter is the finished-project guide) |
| Run artifacts | `runs/` | trial trajectories | Raw per-trial JSONL evidence behind measured arms |
