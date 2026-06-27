# forge-gap — project docs (your learning spine)

These files are the durable **story** of forge-gap, kept in the repo so you can sit down on
any day, in any tab, and instantly know **where we are, why we chose what we chose, and what
every piece means** — without digging through old chat sessions or ephemeral plan files.

Three docs, each with one job:

| File | One job | Read it when… |
|------|---------|---------------|
| [`ROADMAP.md`](ROADMAP.md) | **Where are we?** The stage ladder (S0 → S1 → S2 → …): what each stage does, why, and its status. | You want the map / the big picture. |
| [`DECISIONS.md`](DECISIONS.md) | **Why this choice?** Every real decision, the options weighed, and why one won — in plain English. | You want to understand or push back on a choice. |
| [`LEARNING.md`](LEARNING.md) | **What does it mean?** A plain-English walk-through of each stage, a teaching note, a growing glossary, and recall questions to make it stick. | You want to actually learn / review the material. |

Raw, blow-by-blow notes from individual build sessions live in [`session-logs/`](session-logs/)
(these come from `/wrap`). Those are the unedited recap; the three docs above are the curated
distillation you return to.

## How the spine stays current (the per-stage rhythm)

Every stage (each "S") follows the same beat — the rules live in the project [`CLAUDE.md`](../CLAUDE.md):

- **Start of a stage** → Claude writes the plain-terms brief + the real options into these docs
  **before** coding, so you can weigh in while it still matters.
- **End of a stage** → Claude updates the roadmap, logs the decisions, adds the teaching note +
  new words to the glossary, and asks you 3 recall questions.

Your existing `/begin` reads this spine at the start of a session; `/wrap` updates it at the end.

**Safety net.** Run `uv run check_docs.py` anytime (it's also part of each stage's definition of
done): it flags any stage marked done in `ROADMAP.md` that's missing from `LEARNING.md`, so drift
gets caught even if the rhythm slips. It's a smoke alarm, not a blocker.

## The standing rule

Everything here is written **for someone sharp but new to the jargon** — plain English, every
new term defined the first time, **clearer not longer**. If something here is fuzzy, that's a
bug in the doc, not in you — say so and it gets fixed.
