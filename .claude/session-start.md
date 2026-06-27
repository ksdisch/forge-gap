# Session start — forge-gap

`/begin` should, after the usual orientation (current branch, recent commits, open PRs):

1. **Check the learning spine is current** — run `uv run check_docs.py` and read the result.
2. **Check for concurrent work** — run `git status`; if files you didn't touch are modified or
   untracked, another tab may be working in this same folder. Don't `git add -A`; flag it to
   Kyle. (See the project memory on concurrent sessions / git worktrees.)
3. **Offer the walkthrough if a stage shipped undocumented** — if `check_docs.py` reports a gap,
   or a `feat/sN-*` PR has merged to `main` without a matching `## S<n>` section in
   `docs/LEARNING.md`, proactively tell Kyle and offer to run **`/document-stage`** (it writes
   the stage up, then teaches + quizzes him). This is the moment the teaching actually happens.
4. Follow the **"Working with Kyle"** standard in `CLAUDE.md`: plain English, define every
   jargon term, clearer not longer, and lay out options so he can weigh in.
