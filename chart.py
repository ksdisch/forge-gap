"""chart.py — render the forge-gap gap-closure figure (S5, the deliverable).

Reads the *saved* S4 ablation result (vendored at `docs/figures/gap-closure-data.json`,
a tracked copy of the git-ignored `runs/ablation-summary.json` — see DECISIONS D18) and
draws the project's headline figure: a two-bar task-completion chart, baseline vs
+error-recovery, each bar carrying its **Wilson 95% CI** as a whisker, annotated with the
**Newcombe 95% CI** on the gap between them, plus an honesty caption stating the gap is
*injected*, not natural (the ROADMAP honesty rule).

No model calls, no network — it only plots numbers already measured in S4. Run:

    uv run chart.py            # writes docs/figures/gap-closure.png

The pure label/format helpers (`pct`, `signed_pp`, `fmt_pp_ci`, `bar_label`, `gap_label`,
`caption`, `wilson_yerr`) are matplotlib- and network-free so `test_chart.py` can check
them offline; the actual render lives in `build_figure` and is smoke-verified by running.
"""
from __future__ import annotations

import json
import os

DATA_PATH = os.path.join("docs", "figures", "gap-closure-data.json")
OUT_PATH = os.path.join("docs", "figures", "gap-closure.png")

# S6: the N-bar malformed-call figure (baseline / +error-recovery / +retry-nudge).
MULTI_DATA_PATH = os.path.join("docs", "figures", "malformed-gap-data.json")
MULTI_OUT_PATH = os.path.join("docs", "figures", "malformed-gap.png")

# S8: the N-bar NATURAL-gap figure on a weak model (baseline / +retry-nudge / +submit-nudge, CLEAN task).
WEAK_DATA_PATH = os.path.join("docs", "figures", "weak-gap-data.json")
WEAK_OUT_PATH = os.path.join("docs", "figures", "weak-gap.png")

# S9: the STACKED validation figure (submit-nudge reference vs +validation, CLEAN task, weak model).
VALIDATION_DATA_PATH = os.path.join("docs", "figures", "validation-data.json")
VALIDATION_OUT_PATH = os.path.join("docs", "figures", "validation-gap.png")

# S10: the UN-stacked hallucination figure (bare baseline vs +validation, CLEAN task, llama-3.1-8b).
HALLUCINATION_DATA_PATH = os.path.join("docs", "figures", "hallucination-gap-data.json")
HALLUCINATION_OUT_PATH = os.path.join("docs", "figures", "hallucination-gap.png")

# S11: the CAPSTONE capability-ladder figure — three models on the CLEAN task, baseline vs
# +matched-guardrails per model. Its data JSON is DERIVED, not hand-typed: rebuilt on every run
# from the vendored per-stage JSONs above (DECISIONS D24), so the summary figure can never
# silently drift from the per-stage figures it summarizes.
CAPSTONE_DATA_PATH = os.path.join("docs", "figures", "capstone-data.json")
CAPSTONE_OUT_PATH = os.path.join("docs", "figures", "capstone-ladder.png")

# S3's measured constant: GLM-4.6 aced the clean task 20/20 (DECISIONS D12). That diagnostic
# predates the vendored-summary convention (D18), so the capstone carries it as a documented
# constant rather than a file read — the one hand-typed number in the ladder, disclosed.
GLM_CLEAN_S3 = {"correct": 20, "n": 20}

# Palette: muted gray for the no-help baseline, positive teal for a mechanism that really lifts,
# neutral steel for a mechanism whose gap straddles 0 (a null — colour follows the measured verdict,
# never the hoped-for one, so the figure can't over-claim).
BASELINE_COLOR = "#9e9e9e"
MECHANISM_COLOR = "#2a9d8f"
NULL_COLOR = "#9aa7b4"

# Display names for the malformed figure's x-axis, keyed by arm label.
ARM_DISPLAY = {
    "baseline": "Baseline\n(no mechanism)",
    "error_recovery": "+ Error-recovery\n(harness retry)",
    "retry_nudge": "+ Retry-nudge\n(model re-prompt)",
    "submit_nudge": "+ Submit-nudge\n(prompt to submit)",
}


# --- pure helpers (no matplotlib; unit-tested offline in test_chart.py) -------

def load_summary(path: str = DATA_PATH) -> dict:
    """Load the vendored S4 ablation summary — the figure's single source of truth."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def pct(rate: float, places: int = 1) -> str:
    """A rate in [0, 1] as a percentage string: 0.675 -> '67.5%'."""
    return f"{rate * 100:.{places}f}%"


def signed_pp(value: float, places: int = 1) -> str:
    """A difference in *percentage points*, with an explicit sign: 0.325 -> '+32.5'."""
    return f"{value * 100:+.{places}f}"


def fmt_pp_ci(lo: float, hi: float) -> str:
    """A difference interval in signed percentage points: (0.173, 0.480) -> '[+17.3, +48.0]'."""
    return f"[{signed_pp(lo)}, {signed_pp(hi)}]"


def bar_label(arm: dict) -> str:
    """Two-line data label for a bar: '67.5%\\n(27/40)'."""
    return f"{pct(arm['rate'])}\n({arm['correct']}/{arm['n']})"


def gap_label(gap: dict) -> str:
    """The gap annotation: the closed delta + its Newcombe confidence interval."""
    lo, hi = gap["newcombe"]
    return f"gap {signed_pp(gap['delta'])}%\nNewcombe 95% CI\n{fmt_pp_ci(lo, hi)}"


def caption(s: dict) -> str:
    """The load-bearing honesty caption printed on the figure (the gap is INJECTED)."""
    mech = s["mechanism"]
    return (
        f"N={s['n']} paired seeds  ·  fault-rate {s['fault_rate']}  ·  "
        f"temp {s['temperature']}  ·  {s['model']}\n"
        f"gap is INJECTED (controlled fault-recovery testbed)  ·  "
        f"{mech['recoveries']} transient 503s absorbed at the harness"
    )


def wilson_yerr(arm: dict) -> tuple[float, float]:
    """Asymmetric whisker offsets (lower, upper), in *rate* units, from the bar top
    out to that arm's Wilson bounds. A 100% bar has a one-sided whisker (upper = 0)."""
    lo, hi = arm["wilson"]
    return arm["rate"] - lo, hi - arm["rate"]


# --- S6: pure helpers for the N-bar malformed figure (unit-tested offline) ----

def is_win(arm: dict) -> bool:
    """True if this arm has a measured gap vs baseline whose Newcombe interval clears 0 (a real
    lift). The baseline arm (no `gap_vs_baseline`) and any null arm are False — this drives the
    bar colour, so the figure shows a win only where the statistics actually support one."""
    g = arm.get("gap_vs_baseline")
    return bool(g and g["excludes_zero"])


def gap_tag(arm: dict) -> str:
    """Compact per-mechanism annotation: signed-pp delta, its Newcombe CI, and a real/null verdict."""
    g = arm["gap_vs_baseline"]
    lo, hi = g["newcombe"]
    verdict = "real" if g["excludes_zero"] else "null"
    return f"Δ {signed_pp(g['delta'])} pp\n{fmt_pp_ci(lo, hi)}\n→ {verdict}"


def nudges_spent(s: dict) -> int:
    """Total corrective re-prompts the retry-nudge arm issued (0 if there is no such arm)."""
    for a in s["arms"]:
        if a["label"] == "retry_nudge":
            return a.get("nudges", 0)
    return 0


def multi_caption(s: dict) -> str:
    """The load-bearing honesty caption for the malformed figure: the gap is INJECTED, error-recovery
    structurally cannot fix a malformed call, and retry-nudge paid N model turns to do so."""
    return (
        f"N={s['n']} paired seeds  ·  malformed-call fault-rate {s['fault_rate']}  ·  "
        f"temp {s['temperature']}  ·  {s['model']}\n"
        f"gap is INJECTED (malformed-call testbed)  ·  error-recovery can't fix a malformed call  ·  "
        f"retry-nudge spent {nudges_spent(s)} corrective re-prompts"
    )


# --- S8: pure helpers for the N-bar NATURAL-gap (weak model) figure ----------

def submit_nudges_spent(s: dict) -> int:
    """Total submit-nudges the submit-nudge arm issued (0 if there is no such arm)."""
    for a in s["arms"]:
        if a["label"] == "submit_nudge":
            return a.get("submit_nudges", 0)
    return 0


def weak_caption(s: dict) -> str:
    """Honesty caption for the S8 weak-model figure: the gap is NATURAL — no fault injection at all.
    It states the clean task + model + that the lift came from submit-nudges, and that the residual
    misses are wrong-answer (a *validation* gap submit-nudge can't close) — never claims 'INJECTED'."""
    return (
        f"N={s['n']} runs  ·  CLEAN task, NO fault injection  ·  "
        f"temp {s['temperature']}  ·  {s['model']}\n"
        f"gap is NATURAL (the weak model's own no-submit failure)  ·  "
        f"submit-nudge spent {submit_nudges_spent(s)} re-prompts  ·  residual misses are wrong-answer (validation)"
    )


# --- S9: pure helpers for the STACKED validation figure ----------------------

def validations_spent(s: dict) -> int:
    """Total validation re-prompts the validation arm issued (0 if there is no such arm)."""
    for a in s["arms"]:
        if a["label"] == "validation":
            return a.get("validations", 0)
    return 0


def validation_caption(s: dict) -> str:
    """Honesty caption for the S9 validation figure. The gap is NATURAL (no injection) and the ablation
    is STACKED: the reference arm is itself submit-nudge (the S8 layer) on a model whose BARE baseline is
    0%, so the full ladder is 0% → 75% → 100%. Validation recomputes the total from the model's OWN
    retrieved tool results — a self-consistency check, NEVER the oracle's answer key — so it can be fooled
    by wrong-record retrieval (here retrieval is always correct, so the residual is pure arithmetic slip)."""
    return (
        f"N={s['n']} runs  ·  CLEAN task, NO fault injection  ·  temp {s['temperature']}  ·  {s['model']}\n"
        f"NATURAL gap · ladder 0% (S8 bare) → 75% +submit-nudge → 100% +validation  ·  "
        f"validation recomputes from the model's OWN retrieved data (self-consistency, not the answer key)"
    )


# --- S10: pure helper for the UN-stacked hallucination figure -----------------

def hallucination_caption(s: dict) -> str:
    """Honesty caption for the S10 hallucination figure. The gap is NATURAL (no injection) and UN-stacked:
    llama-8b submits unaided (garbage), so the reference is the bare baseline. Validation recovers only the
    self-consistency-violating slice; the residual is the check's structural blind spot — measured by a
    hand-read of every miss (D23), stated on the figure so a 45% bar can't read as 'validation fixes llama'."""
    return (
        f"N={s['n']} runs  ·  CLEAN task, NO fault injection  ·  temp {s['temperature']}  ·  {s['model']}\n"
        f"NATURAL gap, UN-stacked · the 55% residual is UN-VALIDATABLE (hand-read): "
        f"35% never-retrieved evidence · 10% wrong-record (validator fooled — self-consistent) · "
        f"7.5% non-numeric · 2.5% no-submit"
    )


# --- S11: the capstone capability ladder (derived data + pure helpers) --------

def _arm(s: dict, label: str) -> dict:
    """The arm with this label from an `arms`-shaped summary. Raises StopIteration if absent —
    which is the drift alarm we want: a renamed arm label must break the capstone loudly."""
    return next(a for a in s["arms"] if a["label"] == label)


def _slim(arm: dict) -> dict:
    """Just the fields a capstone bar needs from a vendored arm (correct / n / rate / wilson)."""
    return {k: arm[k] for k in ("correct", "n", "rate", "wilson")}


def build_capstone_data() -> dict:
    """Derive the capstone capability-ladder summary from the vendored per-stage JSONs (D24).

    Nothing here is hand-typed except S3's documented 20/20 (`GLM_CLEAN_S3`, which predates the
    vendoring convention): nemo's bars come straight from the S8/S9 files, llama's from the S10
    file, and the one gap that spans two runs (nemo's S8 baseline vs its S9 stack) is recomputed
    fresh via `stats.newcombe_diff` — a CROSS-RUN comparison, flagged as such so the caption can
    disclose it. GLM gets NO guardrail bar: no guardrail arm was ever run on its clean task
    (there was nothing to close), and drawing one would fabricate a measurement.
    """
    from stats import excludes_zero, newcombe_diff, wilson

    weak = load_summary(WEAK_DATA_PATH)            # S8: nemo's bare baseline (0/20)
    val = load_summary(VALIDATION_DATA_PATH)       # S9: nemo's submit-nudge + validation stack (40/40)
    hall = load_summary(HALLUCINATION_DATA_PATH)   # S10: llama baseline vs +validation (one ablation)

    k, n = GLM_CLEAN_S3["correct"], GLM_CLEAN_S3["n"]
    glm_base = {"correct": k, "n": n, "rate": k / n, "wilson": list(wilson(k, n))}

    nemo_base = _slim(_arm(weak, "baseline"))
    nemo_best = _slim(_arm(val, "validation"))
    d, lo, hi = newcombe_diff(nemo_base["correct"], nemo_base["n"],
                              nemo_best["correct"], nemo_best["n"])
    nemo_gap = {"delta": d, "newcombe": [lo, hi],
                "excludes_zero": excludes_zero(lo, hi), "cross_run": True}

    llama_gap = {**_arm(hall, "validation_only")["gap_vs_baseline"], "cross_run": False}

    return {
        "kind": "capstone-ladder",
        "task": "clean (no fault injection)",
        "temperature": hall["temperature"],
        "models": [
            {"name": "GLM-4.6", "tier": "strong", "model": "z-ai/glm-4.6",
             "baseline": glm_base, "guardrails": None, "gap": None,
             "source": "S3 clean diagnostic",
             "note": "no natural gap — nothing to close"},
            {"name": "mistral-nemo", "tier": "mid", "model": "mistralai/mistral-nemo",
             "baseline": nemo_base,
             "guardrails": {**nemo_best, "label": "+ submit-nudge\n+ validation"},
             "gap": nemo_gap, "source": "S8 baseline · S9 stack (cross-run)"},
            {"name": "llama-3.1-8b", "tier": "weak", "model": "meta-llama/llama-3.1-8b-instruct",
             "baseline": _slim(_arm(hall, "baseline")),
             "guardrails": {**_slim(_arm(hall, "validation_only")), "label": "+ validation"},
             "gap": llama_gap, "source": "S10 (one ablation)"},
        ],
    }


def capstone_caption(s: dict) -> str:
    """Honesty caption for the capstone ladder (D24) — three disclosures, none optional:
    every bar is the CLEAN task; GLM's guardrail win lived on the INJECTED testbed and is
    deliberately not a bar here; nemo's gap is CROSS-RUN (S8 baseline vs S9 stack); and llama's
    partial bar is the blind-spot story (55% un-validatable, decomposed on the S10 figure)."""
    return (
        f"All bars: CLEAN task, NO fault injection  ·  temp {s['temperature']}  ·  "
        f"Wilson 95% whiskers  ·  Newcombe 95% on each gap\n"
        f"GLM-4.6 has no natural gap — its +32.5 pp error-recovery win was on the INJECTED testbed (S4–S5)\n"
        f"nemo gap is CROSS-RUN (S8 baseline N=20 vs S9 stack N=40)  ·  "
        f"llama's 55% residual is un-validatable (decomposed on the S10 figure)"
    )


# --- the figure (matplotlib; smoke-verified by running chart.py) --------------

def build_figure(s: dict, out_path: str = OUT_PATH) -> str:
    """Draw the two-bar gap-closure chart from the summary `s`; write `out_path`."""
    import matplotlib
    matplotlib.use("Agg")  # headless backend: render straight to a file, no display
    import matplotlib.pyplot as plt

    base, mech, gap = s["baseline"], s["mechanism"], s["gap_closure"]
    arms = [base, mech]
    xs = [0, 1]
    heights = [a["rate"] * 100 for a in arms]
    lo_err = [wilson_yerr(a)[0] * 100 for a in arms]
    up_err = [wilson_yerr(a)[1] * 100 for a in arms]

    fig, ax = plt.subplots(figsize=(8.0, 5.5), dpi=150)

    ax.bar(
        xs, heights, width=0.5, color=[BASELINE_COLOR, MECHANISM_COLOR],
        edgecolor="#333333", linewidth=1.0,
        yerr=[lo_err, up_err], capsize=7,
        error_kw=dict(ecolor="#222222", elinewidth=1.6, capthick=1.6),
        zorder=3,
    )

    # Data label above each arm's upper whisker cap (k/N + %).
    for xi, a in zip(xs, arms):
        ax.text(xi, a["wilson"][1] * 100 + 2.5, bar_label(a),
                ha="center", va="bottom", fontsize=11, fontweight="bold", color="#222222")

    # Gap annotation: dashed baseline reference line + a two-headed arrow showing the
    # climb from the baseline rate up to the mechanism rate, labelled with the Newcombe CI.
    base_top, mech_top = base["rate"] * 100, mech["rate"] * 100
    gx = 1.58
    ax.hlines(base_top, -0.25, gx, linestyles="dashed", color="#9e9e9e", lw=1.2, zorder=2)
    ax.annotate("", xy=(gx, mech_top), xytext=(gx, base_top),
                arrowprops=dict(arrowstyle="<->", color=MECHANISM_COLOR, lw=2.0), zorder=4)
    ax.text(gx + 0.10, (base_top + mech_top) / 2, gap_label(gap),
            ha="left", va="center", fontsize=10.5, color="#1d6f66",
            bbox=dict(boxstyle="round,pad=0.4", fc="#e8f5f3", ec=MECHANISM_COLOR, lw=1.0))

    # Axes cosmetics.
    ax.set_xticks(xs)
    ax.set_xticklabels(["Baseline\n(no mechanism)", "+ Error-recovery\n(harness retry)"], fontsize=11)
    ax.set_ylabel("Task completion rate", fontsize=12)
    ax.set_ylim(0, 118)
    ax.set_yticks([0, 20, 40, 60, 80, 100])
    ax.set_yticklabels([f"{t}%" for t in (0, 20, 40, 60, 80, 100)])
    ax.set_xlim(-0.6, 2.7)
    ax.yaxis.grid(True, color="#e9e9e9", lw=1.0)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    fig.suptitle("Closing the reliability gap with error-recovery",
                 fontsize=14, fontweight="bold", y=0.98)
    ax.set_title("GLM-4.6 · multi-step tool task · injected transient-fault testbed",
                 fontsize=10, color="#666666", pad=10)
    fig.text(0.5, 0.015, caption(s), ha="center", va="bottom",
             fontsize=8.5, color="#777777", style="italic")

    fig.tight_layout(rect=(0, 0.07, 1, 0.95))
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_path


def build_multi_figure(s: dict, out_path: str = MULTI_OUT_PATH, *,
                       caption_fn=multi_caption, subtitle: str | None = None,
                       suptitle: str | None = None, arm_display: dict | None = None) -> str:
    """Draw an N-bar ablation from an `arms`-shaped summary `s`; write `out_path`.

    One completion-rate axis, one bar per arm, each with its Wilson whisker + k/N label. Bars are
    coloured by the measured verdict (teal = a real lift, steel = a null), each mechanism carries its
    Newcombe gap vs the shared baseline. Holding the fault fixed and varying only the mechanism is what
    makes the 'each guardrail fixes its own failure' story legible (DECISIONS D19).

    `caption_fn` and `subtitle` let one renderer serve the S6 *injected* malformed figure (the defaults)
    and the S8 *natural*-gap figure (pass `weak_caption` + a clean-task subtitle), so the honesty caption
    always matches the actual testbed. `suptitle` and `arm_display` add the same override seam for the S9
    *stacked* figure, whose reference arm is submit-nudge (not a bare baseline) and whose headline is a
    different claim — so it needs its own title and x-labels while reusing all the drawing logic."""
    import matplotlib
    matplotlib.use("Agg")  # headless backend: render straight to a file, no display
    import matplotlib.pyplot as plt

    arms = s["arms"]
    xs = list(range(len(arms)))
    heights = [a["rate"] * 100 for a in arms]
    lo_err = [wilson_yerr(a)[0] * 100 for a in arms]
    up_err = [wilson_yerr(a)[1] * 100 for a in arms]
    colors = [BASELINE_COLOR if i == 0 else (MECHANISM_COLOR if is_win(a) else NULL_COLOR)
              for i, a in enumerate(arms)]

    fig, ax = plt.subplots(figsize=(9.0, 5.8), dpi=150)
    ax.bar(
        xs, heights, width=0.58, color=colors, edgecolor="#333333", linewidth=1.0,
        yerr=[lo_err, up_err], capsize=7,
        error_kw=dict(ecolor="#222222", elinewidth=1.6, capthick=1.6),
        zorder=3,
    )

    # Data label above each arm's upper whisker cap (% + k/N).
    for xi, a in zip(xs, arms):
        ax.text(xi, a["wilson"][1] * 100 + 2.5, bar_label(a),
                ha="center", va="bottom", fontsize=11, fontweight="bold", color="#222222")

    # Dashed baseline reference line across all arms.
    base_top = arms[0]["rate"] * 100
    ax.hlines(base_top, -0.45, len(arms) - 0.55, linestyles="dashed", color="#9e9e9e", lw=1.2, zorder=2)

    # Per-mechanism gap annotation, low inside each bar, coloured + verdict-tagged.
    for xi, a in list(zip(xs, arms))[1:]:
        col = MECHANISM_COLOR if is_win(a) else NULL_COLOR
        ax.text(xi, 4, gap_tag(a), ha="center", va="bottom", fontsize=9, color="#222222",
                bbox=dict(boxstyle="round,pad=0.35", fc="#f7f7f7", ec=col, lw=1.2))

    display_map = arm_display or ARM_DISPLAY
    ax.set_xticks(xs)
    ax.set_xticklabels([display_map.get(a["label"], a["label"]) for a in arms], fontsize=10.5)
    ax.set_ylabel("Task completion rate", fontsize=12)
    ax.set_ylim(0, 118)
    ax.set_yticks([0, 20, 40, 60, 80, 100])
    ax.set_yticklabels([f"{t}%" for t in (0, 20, 40, 60, 80, 100)])
    ax.set_xlim(-0.7, len(arms) - 0.3)
    ax.yaxis.grid(True, color="#e9e9e9", lw=1.0)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    # Title follows the measured verdict — a win only if some mechanism's gap actually clears 0.
    # An explicit `suptitle` override wins (S9's claim differs from the auto-derived one).
    any_win = any(is_win(a) for a in arms[1:])
    if suptitle is not None:
        _suptitle = suptitle
    elif s["fault_kind"] == "none":  # S8: a natural gap (no injection) reads differently than a fault gap
        _suptitle = ("A matched guardrail closes a weak model's natural gap" if any_win
                     else "No guardrail beats the baseline on the clean task")
    else:
        _suptitle = (f"A matched guardrail closes the {s['fault_kind']}-fault gap" if any_win
                     else f"On {s['fault_kind']} faults, no guardrail beats the baseline")
    fig.suptitle(_suptitle, fontsize=14, fontweight="bold", y=0.98)
    ax.set_title(subtitle or "GLM-4.6 · multi-step tool task · injected MALFORMED-call testbed",
                 fontsize=10, color="#666666", pad=10)
    fig.text(0.5, 0.015, caption_fn(s), ha="center", va="bottom",
             fontsize=8.5, color="#777777", style="italic")

    fig.tight_layout(rect=(0, 0.07, 1, 0.95))
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_path


def build_capstone_figure(s: dict, out_path: str = CAPSTONE_OUT_PATH) -> str:
    """Draw the capstone capability ladder: three model groups on one clean-task axis (D24).

    Five bars — GLM alone (a single 100% baseline: no guardrail arm was ever run on its clean
    task, so a second bar would fabricate a measurement; an annotation carries the finding
    instead), then baseline vs +matched-guardrails for nemo and llama. Bar colour keeps the
    house rule: teal only where the measured gap clears 0 (both real here), grey baselines."""
    import matplotlib
    matplotlib.use("Agg")  # headless backend: render straight to a file, no display
    import matplotlib.pyplot as plt
    from matplotlib.transforms import blended_transform_factory

    glm, nemo, llama = s["models"]

    def _mech_color(m: dict) -> str:
        return MECHANISM_COLOR if m["gap"]["excludes_zero"] else NULL_COLOR

    # (x, bar-dict, colour, per-bar tick label) — grouped per model with a gap between groups.
    bars = [
        (0.0, glm["baseline"], BASELINE_COLOR, "baseline"),
        (1.9, nemo["baseline"], BASELINE_COLOR, "baseline"),
        (2.9, nemo["guardrails"], _mech_color(nemo), nemo["guardrails"]["label"]),
        (4.8, llama["baseline"], BASELINE_COLOR, "baseline"),
        (5.8, llama["guardrails"], _mech_color(llama), llama["guardrails"]["label"]),
    ]

    fig, ax = plt.subplots(figsize=(10.0, 6.2), dpi=150)
    ax.bar(
        [x for x, *_ in bars], [b["rate"] * 100 for _, b, *_ in bars],
        width=0.62, color=[c for *_, c, _ in bars], edgecolor="#333333", linewidth=1.0,
        yerr=[[wilson_yerr(b)[0] * 100 for _, b, *_ in bars],
              [wilson_yerr(b)[1] * 100 for _, b, *_ in bars]],
        capsize=7, error_kw=dict(ecolor="#222222", elinewidth=1.6, capthick=1.6), zorder=3,
    )

    # Data label above each bar's upper whisker cap (% + k/N).
    for x, b, *_ in bars:
        ax.text(x, b["wilson"][1] * 100 + 2.5, bar_label(b),
                ha="center", va="bottom", fontsize=10.5, fontweight="bold", color="#222222")

    # GLM's annotation sits where a guardrail bar would have been — the honest non-bar (D24).
    ax.text(1.0, 55, "no natural gap —\nnothing to close\n(S3 20/20 clean ·\nS7 8/8 + 8/8 hardened)",
            ha="center", va="center", fontsize=9, color="#222222",
            bbox=dict(boxstyle="round,pad=0.4", fc="#f7f7f7", ec=BASELINE_COLOR, lw=1.2))

    # Per-model gap annotation, low inside each guardrail bar (same shape as the N-bar figures).
    for x, m in ((2.9, nemo), (5.8, llama)):
        ax.text(x, 4, gap_tag({"gap_vs_baseline": m["gap"]}),
                ha="center", va="bottom", fontsize=9, color="#222222",
                bbox=dict(boxstyle="round,pad=0.35", fc="#f7f7f7", ec=_mech_color(m), lw=1.2))

    # Per-bar tick labels; model-group names sit below them via a blended transform
    # (x in data coords so it tracks the group, y in axes coords so it clears the labels).
    ax.set_xticks([x for x, *_ in bars])
    ax.set_xticklabels([lbl for *_, lbl in bars], fontsize=9.5)
    group_y = blended_transform_factory(ax.transData, ax.transAxes)
    for cx, m in ((0.0, glm), (2.4, nemo), (5.3, llama)):
        ax.text(cx, -0.14, f"{m['name']}  ({m['tier']})", transform=group_y,
                ha="center", va="top", fontsize=11, fontweight="bold", color="#222222")

    ax.set_ylabel("Task completion rate (clean task)", fontsize=12)
    ax.set_ylim(0, 118)
    ax.set_yticks([0, 20, 40, 60, 80, 100])
    ax.set_yticklabels([f"{t}%" for t in (0, 20, 40, 60, 80, 100)])
    ax.set_xlim(-0.7, 6.5)
    ax.yaxis.grid(True, color="#e9e9e9", lw=1.0)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    fig.suptitle("The capability ladder: guardrail payoff grows as the model weakens",
                 fontsize=14, fontweight="bold", y=0.98)
    ax.set_title("same CLEAN multi-step tool task · matched guardrails per model · S3 / S8+S9 / S10 measured results",
                 fontsize=10, color="#666666", pad=10)
    fig.text(0.5, 0.012, capstone_caption(s), ha="center", va="bottom",
             fontsize=8.5, color="#777777", style="italic")

    fig.tight_layout(rect=(0, 0.12, 1, 0.95))
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_path


def main() -> int:
    s = load_summary()
    out = build_figure(s)
    g = s["gap_closure"]
    verdict = "REAL (clears 0)" if g["excludes_zero"] else "null (straddles 0)"
    print(f"wrote {out}")
    print(f"  baseline        {pct(s['baseline']['rate'])} ({s['baseline']['correct']}/{s['baseline']['n']})")
    print(f"  +error-recovery {pct(s['mechanism']['rate'])} ({s['mechanism']['correct']}/{s['mechanism']['n']})")
    print(f"  gap {signed_pp(g['delta'])}%  Newcombe {fmt_pp_ci(g['newcombe'][0], g['newcombe'][1])}  -> {verdict}")

    # S6: render the malformed-call figure too, if its vendored data is present.
    if os.path.exists(MULTI_DATA_PATH):
        ms = load_summary(MULTI_DATA_PATH)
        mout = build_multi_figure(ms)
        print(f"wrote {mout}")
        for a in ms["arms"]:
            tail = ""
            if "gap_vs_baseline" in a:
                gg = a["gap_vs_baseline"]
                v = "REAL" if gg["excludes_zero"] else "null"
                tail = f"   gap {signed_pp(gg['delta'])} pp {fmt_pp_ci(gg['newcombe'][0], gg['newcombe'][1])} -> {v}"
            print(f"  {a['label']:<16} {pct(a['rate'])} ({a['correct']}/{a['n']}){tail}")

    # S8: render the weak-model NATURAL-gap figure too, if its vendored data is present.
    if os.path.exists(WEAK_DATA_PATH):
        ws = load_summary(WEAK_DATA_PATH)
        wout = build_multi_figure(
            ws, out_path=WEAK_OUT_PATH, caption_fn=weak_caption,
            subtitle="mistral-nemo · multi-step tool task · CLEAN (no injection) · natural no-submit gap")
        print(f"wrote {wout}")
        for a in ws["arms"]:
            tail = ""
            if "gap_vs_baseline" in a:
                gg = a["gap_vs_baseline"]
                v = "REAL" if gg["excludes_zero"] else "null"
                tail = f"   gap {signed_pp(gg['delta'])} pp {fmt_pp_ci(gg['newcombe'][0], gg['newcombe'][1])} -> {v}"
            print(f"  {a['label']:<16} {pct(a['rate'])} ({a['correct']}/{a['n']}){tail}")

    # S9: render the STACKED validation figure too, if its vendored data is present. Its reference arm is
    # submit-nudge (the S8 layer), so the gap it reports is validation's INCREMENTAL lift; the bare 0%
    # baseline lives in the caption's full-ladder line rather than as a bar (DECISIONS D22).
    if os.path.exists(VALIDATION_DATA_PATH):
        vs = load_summary(VALIDATION_DATA_PATH)
        vout = build_multi_figure(
            vs, out_path=VALIDATION_OUT_PATH, caption_fn=validation_caption,
            subtitle="mistral-nemo · CLEAN task · validation stacked on submit-nudge · natural wrong-answer gap",
            suptitle="Validation closes the weak model's residual wrong-answer gap",
            arm_display={
                "submit_nudge": "Submit-nudge\n(gets it to submit — S8)",
                "validation": "+ Validation\n(gets it to submit RIGHT)",
            })
        print(f"wrote {vout}")
        for a in vs["arms"]:
            tail = ""
            if "gap_vs_baseline" in a:
                gg = a["gap_vs_baseline"]
                v = "REAL" if gg["excludes_zero"] else "null"
                tail = f"   gap {signed_pp(gg['delta'])} pp {fmt_pp_ci(gg['newcombe'][0], gg['newcombe'][1])} -> {v}"
            print(f"  {a['label']:<16} {pct(a['rate'])} ({a['correct']}/{a['n']}){tail}")

    # S10: render the UN-stacked hallucination figure too, if its vendored data is present. Unlike S9 the
    # reference arm is the BARE baseline (llama submits unaided — garbage), so the bar gap is validation's
    # lift on a MESSY natural wrong-answer gap; the un-validatable residual is decomposed in the caption
    # from the hand-read of every miss (DECISIONS D23).
    if os.path.exists(HALLUCINATION_DATA_PATH):
        hs = load_summary(HALLUCINATION_DATA_PATH)
        hout = build_multi_figure(
            hs, out_path=HALLUCINATION_OUT_PATH, caption_fn=hallucination_caption,
            subtitle="llama-3.1-8b · CLEAN task · validation un-stacked · natural hallucination gap",
            suptitle="Validation recovers the checkable half of a messy wrong-answer gap",
            arm_display={
                "baseline": "Baseline\n(hallucinates & submits)",
                "validation_only": "+ Validation\n(catches what evidence can check)",
            })
        print(f"wrote {hout}")
        for a in hs["arms"]:
            tail = ""
            if "gap_vs_baseline" in a:
                gg = a["gap_vs_baseline"]
                v = "REAL" if gg["excludes_zero"] else "null"
                tail = f"   gap {signed_pp(gg['delta'])} pp {fmt_pp_ci(gg['newcombe'][0], gg['newcombe'][1])} -> {v}"
            print(f"  {a['label']:<16} {pct(a['rate'])} ({a['correct']}/{a['n']}){tail}")

    # S11: derive + render the CAPSTONE capability ladder, if all three source JSONs are present.
    # capstone-data.json is REWRITTEN from its sources on every run — never hand-edited (D24) —
    # so this summary figure cannot drift from the per-stage figures above.
    if all(os.path.exists(p) for p in (WEAK_DATA_PATH, VALIDATION_DATA_PATH, HALLUCINATION_DATA_PATH)):
        cs = build_capstone_data()
        with open(CAPSTONE_DATA_PATH, "w", encoding="utf-8") as f:
            json.dump(cs, f, indent=2)
            f.write("\n")
        cout = build_capstone_figure(cs)
        print(f"wrote {CAPSTONE_DATA_PATH} (derived)")
        print(f"wrote {cout}")
        for m in cs["models"]:
            b = m["baseline"]
            line = f"  {m['name'] + ' (' + m['tier'] + ')':<22} baseline {pct(b['rate'])} ({b['correct']}/{b['n']})"
            if m["guardrails"]:
                g, gg = m["guardrails"], m["gap"]
                v = "REAL" if gg["excludes_zero"] else "null"
                line += (f" -> +guardrails {pct(g['rate'])} ({g['correct']}/{g['n']})"
                         f"   gap {signed_pp(gg['delta'])} pp {fmt_pp_ci(gg['newcombe'][0], gg['newcombe'][1])} -> {v}")
            else:
                line += "   (no gap to close)"
            print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
