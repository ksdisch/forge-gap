---
description: Open a session — orient on project state (branch, recent commits, open PRs), recap from the last /wrap log, offer an optional recall question, then route into the project's session-start spec (e.g., .claude/session-start.md). Project-agnostic.
argument-hint: "[--audio [short|long]]"
allowed-tools: Bash, Read, Write, Glob, Grep, Skill, ToolSearch, SendUserFile, mcp__plugin_voicemode_voicemode__service
---

Session begin.

Orient yourself silently. Orient me briefly. Route me into the project's
session-start flow. No filler.

## Parse `$ARGUMENTS`
- `--audio` → after printing the step-2 brief, also generate a spoken-audio
  catch-up so I can hear where I'm picking up (see "Audio catch-up" below).
  Optional level: `short` (default) or `long`. Without `--audio`, ignore all
  audio steps — the command behaves exactly as before.

## 1. Orient Claude (do this silently — don't narrate the reads)

- Re-skim `CLAUDE.md` for current phase + hard rules (already in your
  system context; just refresh)
- `git fetch origin && git status --branch`
- `git log --oneline -10`
- `gh pr list --state open --limit 10` (if `gh` is available; otherwise
  skip)
- Read `.claude/session-start.md` if it exists, or `session-start.md` at
  repo root, or any equivalent project-local "how to start a session" doc
  — this is the project's authoritative session-start spec
- Find the most recent wrap log: try `docs/session-logs/`, then
  `.claude/session-logs/`, then a quick scan for any `*session-log*` or
  dated session-recap file. If found, read it end-to-end.

## 2. Brief me — one tight block (should fit on one screen)

- Branch + tree state (clean, or what's uncommitted)
- Last 5 commits, one line each
- Open PRs that involve me — number, title, mergeable state
- If a recent wrap log was found:
  - Paste or summarize its **30-second elevator version** verbatim or
    near-verbatim
  - Cross-check current git state against the wrap's "Suggested next
    moves" and flag any drift (e.g., the wrap said PR #X was open but
    it's now merged; or the wrap said next was Y but a hotfix landed on
    main since)
- If no wrap log was found: say so in one line; don't synthesize a fake
  recap

## 2b. Audio catch-up (only if `--audio` was passed)

After printing the step-2 brief, also produce a spoken catch-up so I can hear
where I'm resuming on the way to my desk. This is an extra artifact; it doesn't
change the brief or the routing below — generate it, then continue to step 3.

1. **Write a speakable script** from what you just briefed — not the on-screen
   block (branch lines and PR numbers read badly aloud). Condense for the ear:
   - `short` (default): one-breath orientation — the branch/tree state in plain
     words plus, if a wrap log was found, its **30-second elevator version** of
     last session (~90s). If no wrap log, just the current-state orientation.
   - `long`: the above **plus the suggested next moves and any drift you flagged**
     (e.g. "the recap said P R forty-two was open but it's merged now") so I hear
     the full picture before picking a path (~3 min).
   - Follow the narrate skill's "Writing for the ear" rules: no Markdown, expand
     paths/branches/PR numbers into speech, drop commit SHAs, open with "Here's
     where you're picking up…" and end on the likely next move.
2. **Hand it to the `narrate` skill** (`~/.claude/skills/narrate/`) with
   `voice=am_adam` and `out=~/Projects/_audio/<ISO-date>-<project>-begin.mp3`.
   The skill ensures Kokoro is up, renders the MP3, and `SendUserFile`s it to me.
3. **One line** with the saved path, then — on its own line, in a fenced code
   block — a ready-to-run play command: `afplay "<full-path>"` (the real absolute
   path) so I can copy-paste it to listen if I want to, then carry on with step 3.
   If Kokoro is unavailable, say so in one line and continue — the on-screen brief
   stands; never claim an MP3 exists if it doesn't (and print no play command).

## 3. Offer one optional recall question (single offer, accept skip cleanly)

- If the most recent wrap log has an "Active recall" section, pick **one**
  question and ask:
  > Recall question from last session: `<question>`. Answer aloud, or say
  > skip.
- If I answer: paste the matching answer-key entry from the wrap. One
  round only, then move on.
- If I say skip / no / nothing actionable: move on without comment.
- If no wrap log or no recall section: silently skip this step entirely.

## 4. Route me into the agenda

- **If a session-start spec was found**: surface the paths it defines
  (Path A, Path B, etc.) as the next choice. Mirror the file's own
  structure; don't paraphrase the paths or pick for me. Pause for my pick.
- **If no session-start spec exists**: present a minimal default — current
  branch state + top 3 backlog items (from `BACKLOG.md` if it exists,
  otherwise from `git log` against open work) + the prompt "What do you
  want to work on?" No recommendation — let me set the agenda.

## 5. Once I pick a path or name a task

- Execute the path's instructions **faithfully** (treat the path text as a
  binding spec — don't summarize it, don't shortcut steps)
- For an open-ended task: confirm a one-sentence interpretation, then
  proceed
- From this point on, `/begin` is done. You're in normal working mode.

## Tone rules

- Tight, structured, no filler. No "great question," no "let me…"
- Don't explain what you're about to do — just do it and report.
- Match my `CLAUDE.md` preferences (lists/tables/headings, concise but
  thorough, explain reasoning when asked, flag rabbit holes).
- The brief in step 2 should fit on one screen. If you need more, you
  picked the wrong altitude.
