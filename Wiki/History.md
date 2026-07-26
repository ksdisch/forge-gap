# History — forge-gap

> How this project got here: a chronological narrative of eras and milestones,
> reconstructed from merged PRs, git history, wrap logs, and the decision ledger.
> PR numbers, merge dates, tags, and SHAs are **Fact** by construction; rationale
> lines carry explicit labels (**Fact** when quoted from a PR body/ledger, **Inference**
> when reconstructed). Decisions are anchored by ID to the project's decision
> ledger (`docs/DECISIONS.md`, D1–D24) — never restated here. **Append-only:** new
> milestones are added at the bottom (above the Mining coverage footer); existing
> entries are never rewritten.

## Origin — 2026-06

Started 2026-06-25 as **harness-lab** (first commit `19647de`: GLM-4.6-via-OpenRouter client + tool-calling smoke test) and renamed to **forge-gap** the next day (`edc0993`). The premise from day one: *reproduce and measure* a known reliability primitive on a multi-step tool task, never invent one — see D1 in `docs/DECISIONS.md`. No kickoff brief exists (nothing under `~/Projects/_kickoffs/`); the earliest documents of intent are the project `CLAUDE.md` (`11823ec`) and `docs/ROADMAP.md`. S0 (client + smoke test) and S1 (bare reason→act→observe loop, `9b748a0`) landed via local merges (`5a68b43`, `bac9026`) before GitHub PRs began.

## Era: Foundations — task, oracle, learning spine (2026-06-25 – 2026-06-27)

The harness got its real task, its fixed ruler, and the docs discipline that governed every later stage. By the end, the clean baseline was measured and the injected-fault pivot was locked.

### S2 — real task + deterministic oracle — 2026-06-26
- **Landed:** chained lookup-then-compute scenario (`scenario.py`), pure deterministic grader (`oracle.py`), scenario-agnostic loop with a stop taxonomy (PR #1)
- **Why:** concentrate failures in the tool-use machinery, graded by a fixed ruler [Fact — PR #1 body] — see D2, D3, D4, D8 in `docs/DECISIONS.md`; run policy per D5
- **Tradeoff:** structured `submit_answer` terminal tool over prose-parsing, paying a changed terminal condition for exact grading [Fact — wrap log `docs/session-logs/2026-06-26-fgap-s2-scenario-oracle.md`]

### Learning spine + freshness gate — 2026-06-26 → 2026-06-27
- **Landed:** in-repo teaching standard + docs spine (PR #2), `check_docs.py` freshness check + definition-of-done (PR #3), S3 spine section (PR #5), auto-trigger stage docs (PR #6)
- **Why:** the project doubles as a learning artifact — a stage isn't done until its spine updates land in the same PR [Fact — CLAUDE.md teaching standard]

### S3 — fault-injection gap diagnostic — 2026-06-27
- **Landed:** seeded transient-503 injector (`faults.py`) + N-trial runner (`runner.py`); GLM-4.6 measured 20/20 clean, 16/20 = 80% under rate-0.5 injection, all misses mechanical (PR #4)
- **Why:** kill-trigger 1 fired (no natural gap), so inject faults first as the reproducible floor, natural gap kept as the stretch [Fact — PR #4 body] — see D10, D12, D13 in `docs/DECISIONS.md` (frontier arm + lean-runner scoping: D9, D11)

## Era: Injected-gap measurement (2026-06-27 – 2026-06-29)

The first guardrail was built, measured with proper proportion CIs, drawn as the headline figure — and the second guardrail delivered the project's first honest null.

### S4 — error-recovery arm + Wilson/Newcombe CIs — 2026-06-27
- **Landed:** `recover` toggle (no-turn harness retry), `stats.py` (Wilson/Newcombe/`excludes_zero`), 2-arm ablation harness; measured 67.5% → 100%, +32.5 pp, Newcombe CI clears 0 (PR #7)
- **Why:** the S3 gap was 100% retry-exhaustion, so a no-turn retry is the matched first arm [Fact — PR #7 body] — see D14, D15, D16, D17 in `docs/DECISIONS.md`

### S5 — the gap-closure chart — 2026-06-28
- **Landed:** `chart.py` + vendored figure data + committed `docs/figures/gap-closure.png` with the INJECTED honesty caption; no new model runs (PR #8)
- **Why:** the figure is the literal deliverable and the data was already saved [Fact — PR #8 body] — see D18 in `docs/DECISIONS.md`

### S6 — retry-nudge on a malformed-call fault: a measured NULL — 2026-06-29
- **Landed:** sticky malformed-call fault, `nudge` toggle, N-arm harness + N-bar chart; all three arms 20/20 — GLM self-heals malformed calls (PR #10; whole-project guide PR #9, visual roadmap PR #11)
- **Why:** a guardrail only earns a bar against a failure it actually fixes, and the pilot caught the null cheaply before the full spend [Fact — PR #10 body] — see D19 in `docs/DECISIONS.md`

## Era: Natural-gap hunt → weak-model pivot (2026-06-29 – 2026-06-30)

The headline stretch — finding GLM's *own* failures — came up empty twice, so the project flipped the variable from task difficulty to model capability, and found its first natural gap.

### S7 — natural-gap hunt: GLM shows no natural gap — 2026-06-30
- **Landed:** hardened tasks v1/v2 (`scenario_hard.py`), pilot runner; GLM-4.6 aced 8/8 on both, bounded-escalation stop rule fired → hunt declared done (PR #12)
- **Why:** pre-committed routing — a fourth robustness signal means injected faults are the honest way to study guardrails on this model [Fact — PR #12 body] — see D20 in `docs/DECISIONS.md`

### S8 — weak-model natural gap: submit-nudge +75 pp — 2026-06-30
- **Landed:** fit pilots exposed a capability cliff (llama-8b hallucinates; mistral-nemo never submits) → new `submit_nudge` guardrail; mistral-nemo 0% → 75%, retry-nudge null in the same run (PR #14; guide refresh PR #13)
- **Why:** nemo's no-submit failure is the most recoverable one possible, and the wrong-guardrail null demonstrates specificity in one experiment [Fact — PR #14 body] — see D21 in `docs/DECISIONS.md`

## Era: Validation closes the thesis (2026-06-30 – 2026-07-04)

The fourth guardrail completed the "each failure class → its matched guardrail" story, was stress-tested on a messier model, and the project declared done on purpose.

### S9 — validation guardrail: +25 pp, the ladder completes — 2026-07-03
- **Landed:** `validate` toggle + `Scenario.validate` (self-consistency recompute from the model's own evidence, never the answer key); stacked ablation on mistral-nemo 75% → 100%, full ladder 0% → 75% → 100% (PR #15; README reconcile PR #16)
- **Why:** closes the last uncovered failure row — wrong answer, no error [Fact — PR #15 body] — see D22 in `docs/DECISIONS.md`

### S10 — validation's blind spot, measured — 2026-07-03
- **Landed:** un-stacked ablation on llama-3.1-8b's hallucination gap: 0% → 45%, +45 pp real; the 55% residual hand-read and decomposed; mid-stage harness fix for array-shaped tool args, disclosed (PR #17)
- **Why:** turn the validator's disclosed blind spot from a caveat into a number [Fact — PR #17 body] — see D23 in `docs/DECISIONS.md`

### S11 — declared done: capstone capability-ladder figure — 2026-07-04
- **Landed:** capstone figure derived entirely from already-measured data (GLM one bar, no fabricated guardrail bar), README §12 one-page story, spine close-out; no new measurements (PR #18)
- **Why:** the thesis closed at S9 and was bracketed at S10; consolidation beats new scope for a learning-and-portfolio artifact [Fact — PR #18 body] — see D24 in `docs/DECISIONS.md`

## Era: Post-completion housekeeping (2026-07-06 – 2026-07-26)

The finished artifact got its hygiene and its documentation layers; no mechanisms or measured numbers changed.

### Repo hygiene + finished-project guide — 2026-07-06
- **Landed:** whole-project guide for the finished repo (PR #19); CI running the 12 offline suites, `uv run pytest` entry point, MIT license, "self-hosted" phrasing fix (PR #20); CLAUDE.md run-note (PR #21)
- **Why:** ranked fixes from the 2026-07-06 project guide's recruiter-lens audit [Fact — PR #20 body]

### Tooling + wiki layers — 2026-07-18 → 2026-07-26
- **Landed:** vendored global Claude Code tooling via /claudify-repo sweep (PR #23); project wiki initialized — PROJECT.md, HANDOFF.md, Sources.md, CLAUDE.md wiring (PR #24)
- **Why:** make the repo self-sufficient for cloud sessions and resumable cold [Inference — from PR #23/#24 bodies]
- **Note:** PR #22 (research paper + presenter pack) remains open and unmerged as of the backfill date

---

## Mining coverage
_Backfilled 2026-07-26 by project-wiki BACKFILL. Entries after this date are
appended live by MAINTAIN._
- PR title sweep: all 23 merged PRs — no cap
- Deep reads: 13 of 23 PRs (#1, #4, #7, #8, #10, #12, #14, #15, #17, #18, #20, #23, #24; size/label/title signal; cap 20)
- Also swept: git log (merges + no-merges, incl. 2 pre-PR local merges), tags (none exist), wrap logs (`docs/session-logs/` — 2 logs), decision ledger `docs/DECISIONS.md` (D1–D24, read for anchor IDs only), `docs/ROADMAP.md`, `docs/LEARNING.md`, project guides (`docs/project-guide/`, 2 dated files)
- Not mined: open PR #22 (unmerged), closed-unmerged PRs, issues
