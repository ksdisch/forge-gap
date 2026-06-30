"""test_chart.py — offline unit tests for the gap-closure figure's pure helpers (S5).

No network, no model, no matplotlib, no pytest — run with `uv run test_chart.py` (same
hand-rolled style as test_stats.py). The figure is the project's *deliverable*, so two
things must never silently break:

  1. the label/format helpers that put numbers on the chart (a wrong format = a wrong-looking
     result), and
  2. the data source — the vendored `docs/figures/gap-closure-data.json` must still carry the
     exact S4 / D17 numbers, or the chart would quietly plot something other than what we
     measured.

The actual matplotlib render is smoke-verified by running `chart.py`; here we only touch the
pure, importable pieces. Exits non-zero if any check fails.
"""
from __future__ import annotations

import sys

from chart import (
    MULTI_DATA_PATH,
    WEAK_DATA_PATH,
    bar_label,
    caption,
    fmt_pp_ci,
    gap_label,
    gap_tag,
    is_win,
    load_summary,
    multi_caption,
    nudges_spent,
    pct,
    signed_pp,
    submit_nudges_spent,
    weak_caption,
    wilson_yerr,
)

_failures: list[str] = []


def check(label: str, cond: bool) -> None:
    print(f"  [{'ok  ' if cond else 'FAIL'}] {label}")
    if not cond:
        _failures.append(label)


def close(a: float, b: float, tol: float = 5e-4) -> bool:
    return abs(a - b) <= tol


def test_pct() -> None:
    print("pct — rate -> percent string")
    check("0.675 -> '67.5%'", pct(0.675) == "67.5%")
    check("1.0 -> '100.0%'", pct(1.0) == "100.0%")
    check("Wilson lower 0.5202 -> '52.0%'", pct(0.52017458088898) == "52.0%")


def test_signed_pp_and_ci() -> None:
    print("signed_pp / fmt_pp_ci — differences in signed percentage points")
    check("0.325 -> '+32.5'", signed_pp(0.325) == "+32.5")
    check("0.17303 -> '+17.3'", signed_pp(0.17303625956430102) == "+17.3")
    check("a negative delta keeps its sign: -0.05 -> '-5.0'", signed_pp(-0.05) == "-5.0")
    check(
        "Newcombe interval -> '[+17.3, +48.0]'",
        fmt_pp_ci(0.17303625956430102, 0.47982541911101995) == "[+17.3, +48.0]",
    )


def test_bar_and_gap_labels() -> None:
    print("bar_label / gap_label — exact on-figure text")
    s = load_summary()
    check("baseline label == '67.5%\\n(27/40)'", bar_label(s["baseline"]) == "67.5%\n(27/40)")
    check("mechanism label == '100.0%\\n(40/40)'", bar_label(s["mechanism"]) == "100.0%\n(40/40)")
    check(
        "gap label == 'gap +32.5%\\nNewcombe 95% CI\\n[+17.3, +48.0]'",
        gap_label(s["gap_closure"]) == "gap +32.5%\nNewcombe 95% CI\n[+17.3, +48.0]",
    )


def test_caption_states_injected() -> None:
    print("caption — carries the load-bearing honesty disclosure")
    cap = caption(load_summary())
    for piece in ("N=40", "fault-rate 0.6", "temp 0.7", "z-ai/glm-4.6", "104 transient 503s"):
        check(f"caption mentions '{piece}'", piece in cap)
    check("caption says the gap is INJECTED (the honesty rule)", "INJECTED" in cap)


def test_wilson_yerr() -> None:
    print("wilson_yerr — asymmetric whisker offsets from the bar top")
    s = load_summary()
    lo, up = wilson_yerr(s["baseline"])
    check("baseline lower offset ~ 0.1548", close(lo, 0.15482541911102))
    check("baseline upper offset ~ 0.1242", close(up, 0.12415683037338))
    lo, up = wilson_yerr(s["mechanism"])
    check("100% bar lower offset ~ 0.0876", close(lo, 0.08762453925039))
    check("100% bar upper offset is exactly 0.0 (a one-sided whisker)", up == 0.0)


def test_vendored_data_matches_d17() -> None:
    print("vendored data — still the exact S4 / D17 numbers (the figure's source of truth)")
    s = load_summary()
    check("model == z-ai/glm-4.6", s["model"] == "z-ai/glm-4.6")
    check("N == 40", s["n"] == 40)
    check("fault_rate == 0.6", s["fault_rate"] == 0.6)
    check("temperature == 0.7", s["temperature"] == 0.7)
    check("baseline 27/40", s["baseline"]["correct"] == 27 and s["baseline"]["n"] == 40)
    check("baseline rate == 0.675", close(s["baseline"]["rate"], 0.675))
    check("mechanism 40/40", s["mechanism"]["correct"] == 40 and s["mechanism"]["n"] == 40)
    check("mechanism rate == 1.0", s["mechanism"]["rate"] == 1.0)
    check("mechanism absorbed 104 recoveries", s["mechanism"]["recoveries"] == 104)
    check("gap delta == 0.325", close(s["gap_closure"]["delta"], 0.325))
    check("gap excludes zero -> a real result", s["gap_closure"]["excludes_zero"] is True)


# --- S6: the N-bar malformed figure's pure helpers ------------------------
def _multi() -> dict:
    """A synthetic `arms`-shaped summary: baseline, a NULL error-recovery arm, a REAL nudge arm."""
    return {
        "model": "z-ai/glm-4.6", "n": 40, "fault_rate": 0.6, "temperature": 0.7,
        "fault_kind": "malformed", "baseline_label": "baseline",
        "arms": [
            {"label": "baseline", "correct": 24, "n": 40, "rate": 0.6,
             "wilson": [0.44, 0.74], "by_stop": {}, "recoveries": 0, "nudges": 0},
            {"label": "error_recovery", "correct": 25, "n": 40, "rate": 0.625,
             "wilson": [0.46, 0.76], "by_stop": {}, "recoveries": 0, "nudges": 0,
             "gap_vs_baseline": {"delta": 0.025, "newcombe": [-0.18, 0.22], "excludes_zero": False}},
            {"label": "retry_nudge", "correct": 38, "n": 40, "rate": 0.95,
             "wilson": [0.83, 0.99], "by_stop": {}, "recoveries": 0, "nudges": 57,
             "gap_vs_baseline": {"delta": 0.35, "newcombe": [0.18, 0.50], "excludes_zero": True}},
        ],
    }


def test_is_win() -> None:
    print("is_win — bar colour follows the measured verdict, never the hoped-for one")
    arms = _multi()["arms"]
    check("baseline (no gap) is not a win", is_win(arms[0]) is False)
    check("a straddles-0 mechanism is not a win", is_win(arms[1]) is False)
    check("a clears-0 mechanism is a win", is_win(arms[2]) is True)


def test_gap_tag() -> None:
    print("gap_tag — per-mechanism delta + Newcombe CI + real/null verdict")
    arms = _multi()["arms"]
    check("real arm -> 'Δ +35.0 pp\\n[+18.0, +50.0]\\n→ real'",
          gap_tag(arms[2]) == "Δ +35.0 pp\n[+18.0, +50.0]\n→ real")
    check("null arm -> 'Δ +2.5 pp\\n[-18.0, +22.0]\\n→ null'",
          gap_tag(arms[1]) == "Δ +2.5 pp\n[-18.0, +22.0]\n→ null")


def test_nudges_and_multi_caption() -> None:
    print("nudges_spent / multi_caption — honesty disclosure for the malformed figure")
    s = _multi()
    check("nudges_spent reads the retry-nudge arm (57)", nudges_spent(s) == 57)
    cap = multi_caption(s)
    for piece in ("N=40", "malformed-call fault-rate 0.6", "temp 0.7", "z-ai/glm-4.6",
                  "57 corrective re-prompts"):
        check(f"caption mentions '{piece}'", piece in cap)
    check("caption says the gap is INJECTED", "INJECTED" in cap)
    check("caption states error-recovery can't fix a malformed call",
          "error-recovery can't fix a malformed call" in cap)


def test_vendored_malformed_matches() -> None:
    print("vendored malformed data — the exact S6 null result (the figure's source of truth)")
    s = load_summary(MULTI_DATA_PATH)
    check("model == z-ai/glm-4.6", s["model"] == "z-ai/glm-4.6")
    check("N == 20", s["n"] == 20)
    check("fault_kind == malformed", s["fault_kind"] == "malformed")
    check("fault_rate == 0.6", s["fault_rate"] == 0.6)
    check("three arms, in order",
          [a["label"] for a in s["arms"]] == ["baseline", "error_recovery", "retry_nudge"])
    check("baseline 20/20 = 100%", s["arms"][0]["correct"] == 20 and s["arms"][0]["rate"] == 1.0)
    check("error_recovery 20/20 = 100%", s["arms"][1]["correct"] == 20)
    check("retry_nudge 20/20 = 100%", s["arms"][2]["correct"] == 20)
    check("retry_nudge fired 26 nudges (the faults DID arm — it just didn't help)",
          s["arms"][2]["nudges"] == 26)
    check("error_recovery gap straddles 0 (null)", s["arms"][1]["gap_vs_baseline"]["excludes_zero"] is False)
    check("retry_nudge gap straddles 0 (null)", s["arms"][2]["gap_vs_baseline"]["excludes_zero"] is False)
    check("retry_nudge delta == 0.0", close(s["arms"][2]["gap_vs_baseline"]["delta"], 0.0))


# --- S8: the N-bar NATURAL-gap (weak model) figure's pure helpers + vendored data ---
def test_submit_nudges_spent_and_weak_caption() -> None:
    print("submit_nudges_spent / weak_caption — honesty disclosure for the NATURAL-gap figure")
    s = load_summary(WEAK_DATA_PATH)
    check("submit_nudges_spent reads the submit-nudge arm (15)", submit_nudges_spent(s) == 15)
    cap = weak_caption(s)
    for piece in ("N=20", "CLEAN task", "temp 0.7", "mistralai/mistral-nemo", "NATURAL"):
        check(f"weak caption mentions '{piece}'", piece in cap)
    check("weak caption never claims the gap is INJECTED (it's natural)", "INJECTED" not in cap)


def test_vendored_weak_matches() -> None:
    print("vendored weak data — the exact S8 natural-gap result (the figure's source of truth)")
    s = load_summary(WEAK_DATA_PATH)
    check("model == mistralai/mistral-nemo", s["model"] == "mistralai/mistral-nemo")
    check("N == 20", s["n"] == 20)
    check("fault_kind == none (clean, no injection)", s["fault_kind"] == "none")
    check("fault_rate == 0.0", s["fault_rate"] == 0.0)
    check("three arms, in order",
          [a["label"] for a in s["arms"]] == ["baseline", "retry_nudge", "submit_nudge"])
    check("baseline 0/20 = 0%", s["arms"][0]["correct"] == 0 and s["arms"][0]["rate"] == 0.0)
    check("retry_nudge gap straddles 0 (null — the wrong guardrail)",
          s["arms"][1]["gap_vs_baseline"]["excludes_zero"] is False)
    check("submit_nudge 15/20 = 75%",
          s["arms"][2]["correct"] == 15 and close(s["arms"][2]["rate"], 0.75))
    check("submit_nudge fired 15 submit-nudges", s["arms"][2]["submit_nudges"] == 15)
    check("submit_nudge gap clears 0 -> a real result",
          s["arms"][2]["gap_vs_baseline"]["excludes_zero"] is True)
    check("submit_nudge delta == 0.75", close(s["arms"][2]["gap_vs_baseline"]["delta"], 0.75))


def main() -> int:
    print("Offline tests: gap-closure figure helpers\n" + "-" * 42)
    for t in (
        test_pct,
        test_signed_pp_and_ci,
        test_bar_and_gap_labels,
        test_caption_states_injected,
        test_wilson_yerr,
        test_vendored_data_matches_d17,
        test_is_win,
        test_gap_tag,
        test_nudges_and_multi_caption,
        test_vendored_malformed_matches,
        test_submit_nudges_spent_and_weak_caption,
        test_vendored_weak_matches,
    ):
        t()
        print()
    print("-" * 42)
    if _failures:
        print(f"{len(_failures)} check(s) FAILED:")
        for f in _failures:
            print(f"  - {f}")
        return 1
    print("All checks passed — figure helpers format correctly and the data matches D17.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
