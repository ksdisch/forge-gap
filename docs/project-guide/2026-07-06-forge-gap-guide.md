# forge-gap — Whole-Project Guide (2026-07-06)

> Supersedes the 2026-06-29 guide (written mid-project, at S6/S7). Since then the project shipped
> S8–S11 and is now **complete — declared done** (PR #18, decision D24). This guide covers the
> finished artifact end to end.

---

## 1. Snapshot (TL;DR)

**forge-gap** is a small Python harness that *reproduces and measures* how much specific
reliability guardrails raise an LLM agent's success rate on a multi-step tool-use task — with
real statistics, not vibes. Stack: Python 3.11 + `uv`, the OpenAI SDK pointed at OpenRouter
(GLM-4.6, mistral-nemo, llama-3.1-8b), matplotlib for figures. Maturity: a **finished measurement
project** (S0→S11, 18 merged PRs, 12 offline test suites, declared done on purpose). Run anything
with `uv run <script>`; regenerate every figure with `uv run chart.py` (no API calls). The single
most interesting thing: **every failure class got its one matched guardrail, each measured under a
pre-registered honesty gate** — and the null results are reported as loudly as the wins.

## 2. Purpose & problem

Agents fail in production for *mechanical* reasons — a flaky tool, a malformed call, a model that
computes the right answer but never submits it. Teams bolt on guardrails (retries, re-prompts,
validators) without knowing what each one actually buys. forge-gap answers that narrowly and
honestly: for one multi-step lookup task, **how many percentage points does each guardrail add,
with confidence intervals, and where does it stop helping?** The framing is deliberate and
load-bearing (D1): *reproduced and measured a known primitive — here is the narrow, measured
delta* — never "I invented this." It doubles as a learning-and-portfolio artifact: every decision
is written down in plain English so the author can defend it line by line.

## 3. Capabilities — current state

Everything below **works today** and is reproducible; nothing is stubbed or flagged-off.

- **A scenario-agnostic agent loop** (`agent.py:178`, `run()`) — reason → act → observe, zero
  mechanisms by default, with four opt-in guardrail toggles: `recover`, `nudge`, `submit_nudge`,
  `validate`. Every step logs to a JSONL trajectory for hand-reading.
- **A frozen task + deterministic grader** — a chained lookup-then-compute task (`scenario.py:32`)
  ending in a `submit_answer` terminal tool, graded by mechanical equality against known ground
  truth (`oracle.py:42`), never an LLM judge.
- **Seeded fault injectors** (`faults.py:48`, `faults.py:95`) — transient 503s (error-recovery's
  target) and sticky malformed-call rejections (retry-nudge's target). Deterministic per seed, so
  failures reproduce on demand.
- **An N-arm ablation harness with honest statistics** — `ablation.py:59` runs arms over identical
  seeded faults; `stats.py` provides Wilson CIs per arm (`stats.py:34`), a Newcombe CI on the gap
  (`stats.py:54`), and `excludes_zero` (`stats.py:78`) as the mechanized "may we claim a result?"
  gate.
- **Six committed figures** (`docs/figures/`), all regenerable offline from vendored JSON via
  `uv run chart.py` — including the capstone capability ladder (`chart.py:448`), whose data file is
  *derived* from the per-stage JSONs on every run (`chart.py:232`) so the summary can't drift.
- **Measured results** (all N≥20, temp 0.7, details in §5): +32.5 pp (error-recovery, injected),
  null (retry-nudge on GLM), +75 pp (submit-nudge, natural), +25 pp and +45 pp (validation, natural,
  best-case and messy-case).
- **Docs freshness tooling** — `check_docs.py` flags any completed stage missing from the learning
  spine.

Not built (recorded in D24 as *future projects*, not gaps): a live capability-ladder sweep across
more models, and a genuinely self-hosted endpoint (the models run via OpenRouter, not local
hardware — the "self-hosted" ambition in early framing was never realized and the docs say so).

## 4. Architecture & how it works

The style is a **layered experiment pipeline around one pure core**: task-as-data → engine →
fault layer → runner → statistics → figure.

```
scenario.py ──► agent.py ──► runner.py ──► ablation.py ──► chart.py
 (task as       (loop +       (N trials,     (arms +          (figures from
  data +         toggles)      JSONL each)    Wilson/Newcombe   vendored JSON,
  validate)                                   via stats.py)     offline)
      ▲              ▲
 faults.py      oracle.py
 (seeded 503 /  (deterministic
  malformed)     grade)
```

The non-obvious mechanisms worth understanding:

1. **Guardrails wrap the loop, never the task.** A `Scenario` is byte-identical across arms; an
   arm is just config (`{label, run_kwargs}`). Both arms of a comparison run the *same* seeded
   fault pattern per trial — a paired design, so the gap isn't muddied by one arm drawing easier
   faults (D15).
2. **The four guardrails differ by *what they cost* and *what they can see*.** Error-recovery
   (`agent.py:101`) retries transient faults at the harness level, spending no model turn and
   leaving no trace in the conversation. Retry-nudge, submit-nudge, and validation each append a
   corrective prompt — costing a model turn — and each fires on a different condition: a *failed*
   call, a *missing* terminal call, and an *inconsistent submitted answer* respectively.
3. **The validator is a self-consistency check, not an answer key** (`scenario.py:171`). It
   recomputes the total from the model's *own retrieved tool results* and never reads
   `ground_truth`. It can be fooled by wrong-record retrieval — and was, live, in S10 — which is
   the proof it isn't cheating.
4. **Figures never call the API.** Measured numbers are vendored into `docs/figures/*-data.json`;
   `chart.py` renders from those. Bar color follows the *measured verdict* (real vs null), so the
   chart can't editorialize.

## 5. Build history & key decisions

Eighteen PRs, each stage opening with a written decision brief before any code. The load-bearing
calls:

- **S0–S2: foundation** (PR #1, D2–D8). Minimal GLM client, bare loop, real task. The defining
  choice: **deterministic oracle over LLM judge** (D2) — an LLM judge is self-graded homework;
  measuring a small delta needs a fixed ruler. Also D3: keep failures *mechanical* (wrong call,
  wrong record), never *cognitive* (hard math) — guardrails can only fix the former.
- **S3: the kill-trigger fires** (PR #4, D12 ⭐). GLM-4.6 scored 20/20 clean — no natural gap
  exists. Rather than quietly hardening until something broke, the pre-registered kill-trigger
  routed to: **inject deterministic faults and say so plainly**, keeping a natural-gap hunt as a
  stretch. Tradeoff taken: a manufactured but reproducible testbed over an uncertain chase;
  honesty preserved by disclosing "injected" on every figure.
- **S4–S5: the first real result** (PRs #7–#8, D14–D18). Error-recovery chosen *before*
  retry-nudge because S3's misses were 100% turn-exhaustion — the failure a no-turn harness retry
  actually fixes. Measured: **67.5% → 100%, +32.5 pp, Newcombe [+17.3, +48.0]** at fault-rate 0.6,
  N=40. Wilson/Newcombe over mean±std (D16) because a pass rate is a proportion and Wald intervals
  misbehave near 0%/100% — exactly this regime.
- **S6: a null, reported as the result** (PR #10, D19). Retry-nudge vs a new sticky malformed-call
  fault: all three arms 100%. GLM reads the error hint as a tool result and self-corrects unaided.
  The finding sharpened the thesis: *a guardrail only earns its keep where the model can't help
  itself.* No tuning-for-a-win — the brief pre-committed to publishing either outcome.
- **S7: no natural gap, twice** (PR #12, D20). Hardened tasks (4- then 5-lookup chains, ~25
  confusable records): GLM aced 8/8 and 8/8. A pre-agreed stop rule (≥7/8) ended the chase —
  evidence-backed "declare done" on the hunt rather than an endless escalation.
- **S8: flip the model, find the cliff** (PR #14, D21 ⭐). Weak-model pilots found a **capability
  cliff** with two failure modes invisible to existing guardrails: llama-8b hallucinates answers;
  mistral-nemo computes 158 correctly then *narrates* "calling submit_answer…" without calling it.
  Pivot: build the matched **submit-nudge**. Measured on nemo, N=20: **0% → 75%, +75 pp
  [+47.8, +88.8]**, while retry-nudge fired zero times in the same run — guardrail specificity in
  one picture.
- **S9: validation completes the thesis** (PR #15, D22 ⭐). A hand-read of all 20 S8 trajectories
  first proved the residual (submitting `140`, shipping forgotten) was pure arithmetic slip on
  correctly-retrieved evidence. The validator recomputes from the model's own observations — two
  bright lines: never read `ground_truth`, name the components but never the sum. Stacked ablation
  (validation needs submit-nudge to unmask the gap), N=40 sized via `stats.py` because N=20 was
  knife-edge: **75% → 100%, +25 pp [+11.1, +40.2]**. Full ladder on nemo: 0% → 75% → 100%.
- **S10: measure the blind spot** (PR #17, D23 ⭐). Same validator, byte-for-byte, on llama-8b's
  messy hallucination gap, un-stacked: **0% → 45%, +45 pp [+28.2, +60.2]** — and the 55% residual
  hand-decomposed: 35% never retrieved the evidence, 10% wrong-record (the validator *fooled*,
  exactly as D22 predicted), 7.5% non-numeric, 2.5% no-submit. S9 alone would over-sell the check;
  S10 calibrates it. Bonus: llama exposed a latent harness bug (tool args as a JSON *array* —
  "parses as JSON" ≠ "is a kwargs object"), root-caused offline, fixed with regression tests,
  disclosed as a no-help fix.
- **S11: stop on purpose** (PR #18, D24). Capstone capability-ladder figure from already-measured
  data only. Two honesty calls at design time: GLM gets **no guardrail bar** (none was ever run on
  its clean task — drawing one would fabricate a measurement), and nemo's +100 pp is labeled
  **cross-run** (S8 baseline vs S9 stack). The capstone JSON is derived, never hand-typed.

## 6. Concepts & vocabulary

| Term | One-line definition | Where it lives here |
| --- | --- | --- |
| **Oracle / ground truth** | Code that already knows the right answer and grades pass/fail mechanically | `oracle.py:42` vs the LLM-judge alternative (D2) |
| **Arm / ablation** | One configuration under test; an ablation compares arms differing by exactly one mechanism | `ablation.py:59`, arms as `{label, run_kwargs}` |
| **Wilson interval** | The honest range a true pass-rate sits in given only N samples | `stats.py:34`, whiskers on every bar |
| **Newcombe interval** | A confidence interval on the *difference* between two proportions | `stats.py:54`, the gap annotation |
| **Straddles zero** | The gap CI includes 0 → report "no clear effect," never a win | `stats.py:78`, the honesty gate (D16) |
| **Mechanical vs cognitive failure** | The machinery of a step broke vs the model genuinely couldn't reason it | D3 — the task keeps math trivial on purpose |
| **Fault injection / transient vs sticky** | Deliberately, reproducibly failing a tool; a 503 clears on retry, a malformed-call rejection only clears on a *corrected* call | `faults.py:48` / `faults.py:95` |
| **Guardrail specificity** | Each guardrail fixes only its matched failure; the wrong one nulls | S6, S8 (retry-nudge fired 0× while submit-nudge lifted +75 pp) |
| **Natural vs injected gap** | The model's own failure on a clean task vs one manufactured by the fault layer | S8–S10 vs S3–S6; disclosed on every figure |
| **Stacked ablation** | The "baseline" already carries one guardrail because it's what unmasks the next failure | S9 (validation on top of submit-nudge) |
| **Self-consistency check** | "Does your answer match the evidence *you* gathered?" — not an answer key; can be fooled by wrong retrieval | `scenario.py:171`, D22's bright lines |
| **Kill-trigger / pilot** | A pre-agreed stop-and-reroute condition; a tiny cheap run gating a costly one | D10/D12; every paid run from S6 on was pilot-gated |
| **Vendored / derived data** | Measured numbers committed as JSON so figures rebuild offline; the capstone JSON is rebuilt from sources on every render | `docs/figures/*-data.json`, `chart.py:232` |
| **Capability cliff** | Models either ace the task or fail it wholesale, with a narrow band between | D21's pilot table |

## 7. Recruiter & hiring-manager lens

**Reads as a strength:**
- **Pre-registered honesty machinery.** Kill-triggers, pilot gates, and a *coded* claim gate
  (`excludes_zero`) — the S6 and S7 nulls are presented as headline findings, not buried. An
  experienced reviewer will recognize this as real experimental discipline, which is rare in
  portfolio AI projects.
- **The decision log.** `docs/DECISIONS.md` records 24 decisions with options weighed, tradeoffs,
  and measured outcomes — including a disclosed process deviation (D14 reversed a planned ordering
  and flagged it). PR bodies match. This is senior-engineer paper trail behavior.
- **Statistics done right for the data type.** Wilson + Newcombe on proportions, N sized with the
  project's own `stats.py` before spending (S9, S10), paired seeds, "N = distinct seeds" stated
  explicitly.
- **Anti-drift plumbing.** Vendored figure data, a derived capstone JSON pinned by a test, a docs
  freshness checker, 12 offline network-free suites, clean secrets hygiene (`.gitignore`,
  `.env.example`), disciplined branch/PR flow with descriptive messages.
- **A real bug story.** The S10 array-args crash: root-caused offline, two regression tests,
  minimal fix routed through an existing path, and disclosed that it adds no help.

**Reads as a weakness / risk / junior smell — and how to talk about it:**
- **No CI.** Tests exist but nothing gates a merge; `.github/` is absent. *Honest framing:*
  single-developer repo, every PR ran the suites locally via `uv run`; adding a GitHub Action that
  runs the 12 offline suites is a ~30-minute fix and the first thing I'd do before showing the repo
  widely. **Fix before showing if possible — it's cheap.**
- **Hand-rolled test scripts, not a pytest suite.** Each `test_*.py` runs standalone; there's no
  single `pytest` entry point or coverage measure. *Framing:* zero-dependency by design and each
  suite is fast and offline; consolidating under pytest is mechanical.
- **One task family.** Every number comes from one lookup-then-compute scenario (plus hardened
  variants). External validity is narrow. *Framing:* deliberate scope — the deliverable is the
  *measurement methodology*, and the claim is always scoped to this testbed; breadth was recorded
  (D24) as a follow-on project, not smuggled in.
- **Small N, wide CIs.** N=20–40 per arm; nemo's 100% arm has a Wilson lower bound of 91.2%.
  *Framing:* the CIs are the point — every claim carries its uncertainty, and N was chosen by
  computing where the interval clears zero, not by budget vibes.
- **Live numbers aren't exactly replayable.** Temp 0.7, stochastic models, third-party OpenRouter
  routes that can change. *Framing:* disclosed (D5); fault patterns are seeded and deterministic,
  the analysis pipeline is fully reproducible from vendored data, and the honest fix for model
  stochasticity is N, not temp 0.
- **Minor:** no LICENSE file; `chart.py` has grown to ~640 lines of figure-specific helpers;
  the pyproject description still says "self-hosted" ambitions the project explicitly didn't
  pursue (D24 discloses this, but a skim-reader might catch the mismatch).

## 8. Interview readiness

Likely questions:
1. Walk me through the architecture — what happens on one trial?
2. Why a deterministic oracle instead of an LLM judge?
3. Your gap is injected — didn't you manufacture your own result?
4. Why Wilson and Newcombe intervals instead of mean ± standard deviation?
5. How is the validation guardrail not just an answer key inside the agent?
6. What surprised you most?
7. Tell me about a bug you found and fixed.
8. What would you do differently or next?

---

**Answer scaffolds:**

1. *One trial:* `run_arm` (`runner.py:42`) builds a fresh `Scenario` (optionally fault-wrapped with
   that trial's seed), hands it to `agent.run` with the arm's toggles, the loop alternates model
   turns and tool dispatches logging JSONL each step, the terminal `submit_answer` ends it, and
   `oracle.grade` scores the submitted number against ground truth. `ablation.py` repeats that for
   each arm over the *same* seeds and computes Wilson/Newcombe.
2. *Oracle:* an LLM judge shares blind spots with the system under test and adds noise — self-graded
   homework. Measuring a small delta needs a fixed ruler; here pass/fail is mechanical equality
   against a known answer (D2).
3. *Injected:* yes for S3–S6, and every figure says so in its caption — that's the point. GLM had
   no natural gap (20/20, then 8/8 twice on hardened tasks), so injection was the only reproducible
   testbed, and it doubles as the dev fixture. The natural-gap results (S8–S10) came later by
   swapping in weaker models on the *clean* task — no injection, disclosed separately.
4. *Stats:* completion rate is a proportion; near 0% or 100% with small N, mean±std (and Wald
   intervals) misbehave — they can exceed [0,1] and understate uncertainty, exactly our regime.
   Wilson behaves at the edges; Newcombe carries that into the difference, which is the number we
   report; and `excludes_zero` mechanizes "a bar whose CI overlaps its neighbor is not a result."
5. *Validation:* two bright lines in code — it never reads `scenario.ground_truth`, only the
   model's own retrieved observations; and the re-prompt names the components, never the sum. The
   proof it isn't an answer key: it got *fooled* in S10 — accepted self-consistent-but-wrong 152s
   from wrong-zone retrievals, which the oracle then failed. An answer key can't be fooled.
6. *Surprise:* the S6 null — GLM self-heals malformed calls by reading the error hint as a tool
   result, so the guardrail built for that failure had literally nothing to do. It reframed the
   whole project: guardrails pay off only where the model can't help itself, which is why the
   capstone is a *capability ladder*.
7. *Bug:* llama-8b emitted tool arguments as a JSON array — `["ORD-204"]` — which parses fine but
   isn't a kwargs object; the harness conflated "parses as JSON" with "arguments OK" and crashed on
   `args.get()`. Reproduced offline with two regression tests, fixed by routing non-dict args down
   the existing malformed-arguments path, and disclosed that the fix adds no help — it just stops
   the crash.
8. *Differently/next:* add CI first; then either the live capability-ladder sweep or a genuinely
   self-hosted endpoint — both consciously recorded in D24 as *new projects* so this one could end
   as a clean, defensible artifact instead of an open-ended chase.

## 9. Talking points

**Elevator (~30–60s, spoken):**
"forge-gap is a measurement harness I built to answer a question teams usually hand-wave: when you
bolt a reliability guardrail onto an LLM agent — a retry, a re-prompt, a validator — how many
percentage points does it actually buy? I built a bare agent loop with zero help, a deterministic
grader — never an LLM judge — and then added four guardrails one at a time, each measured against
a baseline with proper confidence intervals. The headline results: a harness-level retry closed an
injected fault gap by thirty-two points; a submit-nudge took a weak model from zero to
seventy-five percent on its own natural failure; and a self-consistency validator closed the rest
— one hundred percent on a clean gap, forty-five on a messy one, with the other fifty-five percent
decomposed by hand into exactly what a validator structurally can't see. Two of the six
experiments were nulls, and they're reported as headline findings — the honesty machinery is the
part I'm proudest of."

**Deep cut (~2 min):** the validation story. S8 left a residual: mistral-nemo, even when nudged to
submit, sometimes submitted 140 — the item total with shipping forgotten. A wrong answer that
throws no error is invisible to every error-based guardrail. The obvious fix — check the answer —
has an integrity trap: if the checker knows the right answer, you've just hidden the answer key
inside the agent and forced a fake 100%. The design that avoids it: recompute the total from the
model's *own retrieved tool results*, never the ground truth, and on a mismatch re-prompt naming
the components but never the sum. That makes it a deployable self-consistency check with a known
blind spot — wrong-record retrieval produces a self-consistent wrong answer it will accept. S9
measured the best case: plus twenty-five points, 100% on the clean-slip gap. S10 stress-tested it
on llama-8b's hallucination mess: plus forty-five points, and the fooling scenario happened live —
the validator accepted a self-consistent 152 built on the wrong zone's rate, which the oracle
failed. That fooled run is the proof of integrity, and the 55% residual became a *measured
number* instead of a caveat. That pair — best case and calibrated worst case — is what makes the
result defensible.

## 10. Gaps, debt & next moves

1. **Add CI** (GitHub Action running the 12 offline suites on PR) — ~30 min, do it before sharing
   the repo. Highest signal-per-effort.
2. **Add a LICENSE** and fix the stale "self-hosted" phrase in `pyproject.toml` — trivial.
3. **Consolidate tests under pytest** with one entry point — low effort, mechanical.
4. **The D24 roads not taken**, each a *new project decision by design*: a live capability-ladder
   sweep (medium effort, mostly harness reuse + API spend) and a genuinely self-hosted endpoint via
   llama.cpp/Ollama (the biggest lift; would finally earn the "Forge" name).

Known debt is otherwise light: `chart.py` (~640 lines) accretes per-figure caption helpers and
would want splitting if a seventh figure ever landed; `runs/` accumulates stale trajectories
locally (gitignored; move aside before hand-reading a fresh run).

## 11. Map of the codebase

| Path | What it is |
| --- | --- |
| `glm.py` | Minimal OpenRouter client (`chat()`, `MODEL`); `max_retries=8` is HTTP hygiene, not a mechanism |
| `agent.py` | The loop + grading; four opt-in guardrail toggles, all off by default; JSONL trajectory per run |
| `scenario.py` / `scenario_hard.py` | The frozen S2 task (+ `Scenario.validate`) / the S7 hardened variants |
| `oracle.py` | Deterministic grader — computed value vs known ground truth |
| `faults.py` | Seeded injectors: transient 503s (`with_faults`) and sticky malformed calls (`with_malformed_faults`) |
| `runner.py` | N-trial runner for one arm; raw k/N + per-trial JSONL |
| `stats.py` | Wilson, Newcombe, `excludes_zero` — the honesty gate |
| `ablation.py` | N-arm harness over identical seeds; arms are config |
| `malformed_ablation.py` / `weak_ablation.py` / `validation_ablation.py` / `hallucination_ablation.py` | The S6 / S8 / S9 / S10 experiments, one thin runner each |
| `chart.py` | All six figures from vendored JSON; derives `capstone-data.json`; no API |
| `pilot.py` / `verify.py` / `check_docs.py` | S7 natural-gap pilot / smoke test / docs freshness check |
| `test_*.py` (12 suites) | Offline, network-free; run each with `uv run test_<name>.py` |
| `docs/` | The learning spine: `ROADMAP.md`, `DECISIONS.md` (D1–D24), `LEARNING.md`, `figures/`, `session-logs/`, `project-guide/` |
