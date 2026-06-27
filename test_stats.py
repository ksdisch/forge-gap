"""test_stats.py — offline unit tests for the proportion CIs (Wilson + Newcombe).

No network, no model, no pytest — run with `uv run test_stats.py` (same hand-rolled style as
test_runner.py). These intervals are the project's *ruler*: if the math is off, every
gap-closure claim downstream is wrong. So we pin the functions to hand-computed reference
values (95%, z = 1.96) and to the edge cases that break the naive ±std approach.

Exits non-zero if any check fails.
"""
from __future__ import annotations

import sys

from stats import excludes_zero, newcombe_diff, wilson

_failures: list[str] = []


def check(label: str, cond: bool) -> None:
    print(f"  [{'ok  ' if cond else 'FAIL'}] {label}")
    if not cond:
        _failures.append(label)


def close(a: float, b: float, tol: float = 5e-4) -> bool:
    return abs(a - b) <= tol


def test_wilson_known_values() -> None:
    print("wilson — hand-computed reference values (95%)")
    # p = 0.5, n = 20 -> symmetric around 0.5, ~(0.299, 0.701)
    lo, hi = wilson(10, 20)
    check("10/20 lower ~ 0.2993", close(lo, 0.2993))
    check("10/20 upper ~ 0.7007", close(hi, 0.7007))
    check("10/20 symmetric around 0.5", close((lo + hi) / 2, 0.5))

    # p = 0.8, n = 20 (S3's baseline) -> ~(0.584, 0.919)
    lo, hi = wilson(16, 20)
    check("16/20 lower ~ 0.5840", close(lo, 0.5840))
    check("16/20 upper ~ 0.9193", close(hi, 0.9193))


def test_wilson_edges() -> None:
    print("wilson — edges stay inside [0, 1] (where ±std fails)")
    lo, hi = wilson(0, 20)
    check("0/20 lower clamps to 0.0", lo == 0.0)
    check("0/20 upper ~ 0.1611 (not 0)", close(hi, 0.1611))

    lo, hi = wilson(20, 20)
    check("20/20 upper clamps to 1.0", hi == 1.0)
    check("20/20 lower ~ 0.8389 (not 1)", close(lo, 0.8389))

    lo, hi = wilson(0, 0)
    check("n=0 -> full range (0,1)", lo == 0.0 and hi == 1.0)

    for k, n in [(0, 5), (3, 5), (5, 5), (7, 13), (40, 40)]:
        lo, hi = wilson(k, n)
        check(f"{k}/{n} stays within [0,1] and lo<=hi", 0.0 <= lo <= hi <= 1.0)


def test_newcombe_overlap_case() -> None:
    print("newcombe — S3's mild gap (16/20 vs 20/20) straddles 0 -> 'not a result'")
    d, lo, hi = newcombe_diff(16, 20, 20, 20)  # baseline 80% vs mechanism 100%
    check("point estimate d == 0.20", close(d, 0.20))
    check("interval lower ~ -0.0005 (just below 0)", close(lo, -0.0005))
    check("interval upper ~ 0.4160", close(hi, 0.4160))
    check("includes 0 -> excludes_zero is False", excludes_zero(lo, hi) is False)


def test_newcombe_clear_case() -> None:
    print("newcombe — a crisp gap (24/40 vs 38/40) excludes 0 -> a real result")
    d, lo, hi = newcombe_diff(24, 40, 38, 40)  # baseline 60% vs mechanism 95%
    check("point estimate d == 0.35", close(d, 0.35))
    check("interval lower ~ 0.171 (> 0)", close(lo, 0.171, tol=2e-3))
    check("interval upper ~ 0.508", close(hi, 0.508, tol=2e-3))
    check("excludes 0 -> a real result", excludes_zero(lo, hi) is True)


def test_excludes_zero_logic() -> None:
    print("excludes_zero — the honesty gate")
    check("(0.1, 0.4) excludes 0", excludes_zero(0.1, 0.4) is True)
    check("(-0.4, -0.1) excludes 0 (a real *negative* effect)", excludes_zero(-0.4, -0.1) is True)
    check("(-0.05, 0.30) straddles 0", excludes_zero(-0.05, 0.30) is False)
    check("(0.0, 0.30) touching 0 is NOT a clear result", excludes_zero(0.0, 0.30) is False)


def main() -> int:
    print("Offline tests: proportion confidence intervals\n" + "-" * 46)
    for t in (
        test_wilson_known_values,
        test_wilson_edges,
        test_newcombe_overlap_case,
        test_newcombe_clear_case,
        test_excludes_zero_logic,
    ):
        t()
        print()
    print("-" * 46)
    if _failures:
        print(f"{len(_failures)} check(s) FAILED:")
        for f in _failures:
            print(f"  - {f}")
        return 1
    print("All checks passed — Wilson + Newcombe match references and behave at the edges.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
