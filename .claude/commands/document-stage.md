---
description: Document a just-finished stage in the learning spine, then teach + quiz Kyle
argument-hint: "[stage, e.g. S3 — optional; inferred from git if omitted]"
---

Run the per-stage documentation + teaching ritual for forge-gap. Follow the **"Working with
Kyle"** standard in `CLAUDE.md` throughout: plain English, define every jargon term the first
time it appears, clearer not longer.

**Target stage:** $ARGUMENTS — if empty, infer it (the `docs/ROADMAP.md` row marked "in
progress", or the most recently merged `feat/sN-*` PR). If it is ambiguous, ask Kyle which stage.

Do this in order:

1. **See what's missing.** Run `uv run check_docs.py`. If it already passes and the stage is
   fully written up (the stage's own session may have done it), skip steps 3–4 and go straight
   to the teach + quiz.
2. **Understand what was actually built.** Read the stage's real changes — the merged PR diff
   and/or the new/changed source files. Never describe code you have not read.
3. **Update the spine** (plain English, per the standard):
   - `docs/ROADMAP.md` — flip the stage's status to done (✅); refresh "where we are".
   - `docs/DECISIONS.md` — ensure each real choice in the stage has an entry: the choice, the
     options weighed, and why.
   - `docs/LEARNING.md` — add a `## S<n>` section (what we built, the teaching note, the new
     words, and 3 recall questions + answer key); add new terms to the glossary.
4. **Confirm.** Re-run `uv run check_docs.py`; it must pass.
5. **Teach + quiz Kyle — the point of this.** Walk him through the stage in plain English,
   defining each new term, then ask the 3 recall questions one at a time, let him answer, and
   confirm/correct. Active recall, not a lecture.
6. **Land it safely.** Commit the doc updates on a `docs/sN-writeup` branch and open a PR.
   CONCURRENCY: another tab may be editing this folder — run `git status` first, `git add`
   ONLY the doc files by name (never `git add -A`), and merge on the remote (`gh pr merge`);
   do not run `git checkout main && git pull` while foreign changes are uncommitted. (Project
   memory: concurrent-sessions-shared-worktree.)
