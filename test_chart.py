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
    bar_label,
    caption,
    fmt_pp_ci,
    gap_label,
    load_summary,
    pct,
    signed_pp,
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


def main() -> int:
    print("Offline tests: gap-closure figure helpers\n" + "-" * 42)
    for t in (
        test_pct,
        test_signed_pp_and_ci,
        test_bar_and_gap_labels,
        test_caption_states_injected,
        test_wilson_yerr,
        test_vendored_data_matches_d17,
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
