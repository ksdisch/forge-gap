---
description: Generate a self-contained handoff prompt I can paste into a fresh Claude Code session to continue this work without losing context. Captures hard-won lessons, what's done, and where the plan stands. Also prints a short plain-English 'what's next & why' briefing for me, so I stay oriented across the handoff. Stops the current work after generating. Project-agnostic.
argument-hint: "[--audio [short|long]]"
allowed-tools: Bash, Read, Write, Glob, Grep, Task, Skill, ToolSearch, SendUserFile, mcp__plugin_voicemode_voicemode__service
---

Context handoff.

## Parse `$ARGUMENTS`
- `--audio` → after printing the handoff, also generate a spoken-audio version
  of the brief (see "Audio narration" at the end). Optional level: `short`
  (default) or `long`. Without `--audio`, ignore all audio steps entirely —
  the command behaves exactly as before.

I'm stopping here to switch to a fresh Claude Code session. Generate a
self-contained prompt I can paste into a new session so it picks up exactly
where we left off — no rediscovery, no repeated mistakes, no preamble.

Write for a fresh AI session, not a human reader. The fresh session has zero
memory of this conversation but has the same file/git access. Include only
what the fresh session cannot derive from `git status`, `git log`,
`gh pr list`, or reading the repo cold. Skip anything obvious from those.

## Before writing — orient silently

- `git status --branch` and `git log --oneline -10` to confirm the current
  branch/tree state and recent commits this session produced
- `gh pr list --state open --limit 10` if `gh` is available
- Re-skim any plan / source-of-truth file the session has been working from
  (e.g. `docs/<topic>-plan.md`, `BACKLOG.md`, an open PR body) — the fresh
  session will need its path
- Mine THIS conversation for landmines: hooks that blocked, commands that
  failed and then worked, decisions made, things the user explicitly said
  "do/don't do." These are the hard-won lessons. They are not in git.

## Output format

Print the handoff as a single fenced code block so I can copy it verbatim —
and print it **LAST**, so it's the final thing in the response, right above my
prompt box. Before the block, in this order: (1) the "For Kyle" briefing (see
"'For Kyle' briefing" below), then (2) the short run-config recommendation
described in "Run-config recommendation" below (2–4 lines), then (3) the audio
note **only if `--audio` was passed** (see "Audio narration") — all OUTSIDE
the block, notes to me, not part of the paste-able prompt; none of these
pollute the block. Then the fenced block, with nothing after it. Once it's
printed, **STOP** — do not continue the current work and do not ask "what's
next." I'll start a fresh session.

Match my CLAUDE.md preferences: structured, concise but thorough, no filler,
name tradeoffs, quote exact paths/branches/PRs/commands rather than
paraphrasing.

## Handoff structure (sections, in order, inside the code block)

1. **Title** — `# Context handoff — <project>: <one-line topic>`

2. **Overview (2–4 sentences)** — what the project is in plain language,
   what's being continued, and the source-of-truth doc/file the fresh
   session should read first. Name the plan file and say what role it plays
   (e.g. "tracks status in a `## Changelog` section at the top").

3. **What's done** — terse bullets of work completed this session. Quote
   exact PR numbers, commit refs, file paths, branch names. Group by PR or
   branch if multiple are in play. Artifacts only, no subjective spin.

4. **Hard-won lessons (apply these)** — the most important section after the
   plan-stands one. Capture gotchas, workarounds, and conventions discovered
   THIS session that a fresh session would otherwise re-hit. Each bullet:
   - Quotes the exact command, file path, hook name, or error message
   - Frames as "X is the case; do Y" or "Z breaks; the path that works is …"
   - Examples worth capturing: pre-commit/push hooks that block direct push,
     repo-specific merge workflow (squash vs merge, branch naming, base
     branch), tools/CLIs the repo expects, env vars that must be set, files
     whose contents look authoritative but aren't, decisions already made
     under uncertainty (so the fresh session doesn't relitigate them),
     things I explicitly told you to do or not do
   - Skip generic advice — only session-specific landmines

5. **Where the plan stands** — the load-bearing section. Be specific:
   - What's in progress right now (file, branch, PR, line of work)
   - The next concrete action, as one imperative sentence
   - What's blocked and on what
   - Any decisions pending me — mark these clearly so the fresh session
     asks before acting, doesn't assume
   - The 1–3 files/branches/PRs the fresh session should open first

## Length

A few hundred words is normal. If the handoff is creeping past ~600 words,
you're including things derivable from git — cut those. If it's under ~150
words, you're probably missing the hard-won lessons — mine the conversation
harder.

## Honesty rules

If something is half-done or wrong, say so. If a decision was made under
uncertainty, flag the assumption so the fresh session can revisit. Don't
paper over gaps to make the handoff look tidy — gaps are exactly what the
fresh session needs to know about.

## "For Kyle" briefing (printed FIRST, at the top of the response)

Open the response with a short plain-English briefing addressed to me — before
the fenced block, never part of the paste. It's the human-facing twin of the machine handoff: its job
is to keep me oriented and engaged across the session boundary, the way a project's
`LEARNING.md` does. Label it clearly so I know it's for me, not for the paste:

> **📋 For Kyle — what the next session will build, and why**

Cover, in 4–6 lines / ~120 words max:
- **What** it's about to build — the next chunk of work, in plain language.
- **How** — the approach in one sentence (the shape of it, not step-by-step).
- **Why** — the reasoning/motive: why this, why now, what it unblocks or proves.

Voice: explain it like I'm sharp but new to the jargon — plain English, define any term the
first time, clearer not longer. It's the plain-English distillation of "Where the plan stands"
(the next concrete action) — the forward-looking "what's coming + why," not a recap of what's
done. If the next step is genuinely uncertain or pending my decision, say that plainly instead
of inventing a plan.

## Run-config recommendation (the second note, still before the code block)

After the "For Kyle" briefing, print a 2–4 line note — OUTSIDE the block, addressed to
me — telling me how to RUN the fresh session. It is never part of the
paste-able prompt (the fresh session can't set its own model/effort). Base the
pick on the *nature of the next concrete action* from "Where the plan stands,"
not on this session's work. Use this shape:

- **Model:** default **Opus 4.8 (1M context)**. Keep "(1M context)" whenever the
  fresh session must read a lot of source / long docs / a big plan to orient;
  drop to plain Opus 4.8 only for a small, self-contained next task.
- **Effort:** pick exactly ONE and name it —
  - **ultracode** (multi-agent fan-out + adversarial verify; highest token cost):
    the next task is broad, parallelizable, or wants exhaustive coverage with
    independent verification — a multi-file audit/migration, a "find every X"
    sweep, a batch where each item is verified against HEAD, a comprehensive
    review. Pick when completeness across many surfaces beats speed.
  - **max effort** (deep single-agent reasoning, no fan-out): the next task is
    ONE hard problem — subtle root-cause debugging, tricky merge/algorithm
    logic, untangling a confusing module, a design call with real tradeoffs.
  - **standard**: mechanical or checklist-scoped work — a known small edit, a
    doc update, wiring a module per a fixed checklist, a straightforward test
    add. Don't pay for reasoning the task doesn't need.
- **Why (one clause):** tie the pick to the specific next action you named, so I
  can sanity-check it — e.g. "max effort: 3 findings in 2 files, each just needs
  verify-against-HEAD + a minimal fix; too narrow to want fan-out."

Keep it terse, like the rest of the handoff. If the next action is genuinely
ambiguous between two modes, name both and say what tips it.

## Audio narration (only if `--audio` was passed)

Generate a spoken version of the brief so I can listen to it on a walk instead
of reading the block. Render the MP3 BEFORE printing the code block; its chat
note (path + play command) goes after the run-config note, so the paste-able
block stays the last thing in the output. It never changes the other sections'
content.

1. **Write a speakable script** — NOT the paste-able block (that's written for a
   fresh AI; reading its scaffolding aloud is useless). Condense for the ear:
   - `short` (default): just the **Overview** — what this work is and what's
     being continued, in 2–4 spoken sentences (~90s).
   - `long`: the Overview **plus Where the plan stands** — the next concrete
     action, anything blocked, and any decision pending me (~3–4 min).
   - Follow the narrate skill's "Writing for the ear" rules: no Markdown, expand
     paths/branches/PR numbers into speech, drop commit SHAs and command blocks,
     open with "Here's where things stand…" and close on the one next thing.
2. **Hand it to the `narrate` skill** (`~/.claude/skills/narrate/`) with
   `voice=am_adam` and `out` = next to wherever this project saves session
   artifacts if there's a convention, else
   `~/Projects/_audio/<ISO-date>-<project>-handoff.mp3`. The skill ensures Kokoro
   is up, renders the MP3, and `SendUserFile`s it to me.
3. **One line in chat** with the saved path, then — on its own line, in a fenced
   code block — a ready-to-run play command: `afplay "<full-path>"` (the real
   absolute path). That way I can copy-paste it to listen if I want to, or ignore
   it. If Kokoro is unavailable, say so plainly — the text handoff still stands;
   don't claim an MP3 exists if it doesn't (and print no play command).
