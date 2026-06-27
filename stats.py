"""stats.py — proportion confidence intervals for the gap-closure measurement (S4).

A completion rate is a **proportion**: k successes out of n tries. It is NOT a normal
"average," so the familiar mean ± standard-deviation is the wrong ruler for it (it can hand
you an interval that runs below 0% or above 100%, which is nonsense for a rate). This module
gives the right rulers:

  - `wilson(k, n)` — the **Wilson score interval**: the honest range a single arm's *true*
    pass-rate likely sits in, given only n samples. Well-behaved at the edges (k=0 or k=n) and
    never escapes [0, 1], which is exactly where ±std falls apart.

  - `newcombe_diff(...)` — the **Newcombe interval** for the *difference* between two arms'
    rates (mechanism minus baseline). This is the number the whole project turns on: "the
    guardrail added X percentage points, and here's the honest ± on that X." If that interval
    straddles 0, we cannot claim the guardrail helped — `excludes_zero(...)` is that test.

Why these two specifically (DECISIONS D7): measuring a *small* delta between two arms needs
intervals that stay sane with few samples and near 0%/100% — precisely the Wilson/Newcombe
regime. Pure functions, no model, no network: trivially unit-tested (test_stats.py).

Plain-English terms:
  - *proportion* — a fraction of successes, k/n.
  - *confidence interval (CI)* — the honest range the true value likely sits in given only n
    samples; here we use the conventional 95% level (z = 1.96).
  - *z* — how many standard-normal widths the interval spans; z = 1.96 is the 95% two-sided value.
"""
from __future__ import annotations

import math

Z_95 = 1.96  # two-sided 95% standard-normal critical value


def wilson(k: int, n: int, z: float = Z_95) -> tuple[float, float]:
    """Wilson score interval (lo, hi) for a proportion k/n at confidence level `z`.

    The interval is centred on a slightly shrunk estimate (pulled toward 1/2) and is asymmetric
    near the edges — which is the honest behaviour: 20/20 successes does NOT mean the true rate
    is exactly 100%, so the lower bound sits sensibly below 1.0 rather than collapsing. Always
    inside [0, 1].

    `n = 0` returns (0.0, 1.0): with no data we know nothing, so the interval is the whole range.
    """
    if n <= 0:
        return (0.0, 1.0)
    phat = k / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (phat + z2 / (2 * n)) / denom
    half = (z / denom) * math.sqrt(phat * (1 - phat) / n + z2 / (4 * n * n))
    return (max(0.0, center - half), min(1.0, center + half))


def newcombe_diff(
    k_base: int, n_base: int, k_mech: int, n_mech: int, z: float = Z_95
) -> tuple[float, float, float]:
    """Newcombe interval for the difference d = p_mech - p_base. Returns (d, lo, hi).

    `d` is the point estimate of how much the mechanism arm beats the baseline arm (positive =
    the guardrail helped). `(lo, hi)` is the honest range on that difference. This is Newcombe's
    "square-and-add" method (his method 10): it combines each arm's own Wilson interval rather
    than assuming a single pooled normal spread, which keeps it trustworthy even when an arm
    sits near 0% or 100% and when n is small — exactly our situation.

    Convention: arm 1 = baseline (k_base/n_base), arm 2 = mechanism (k_mech/n_mech), so a
    positive `d` (and a `(lo, hi)` that stays above 0) means the mechanism measurably helped.
    """
    p1 = k_base / n_base if n_base else 0.0   # baseline
    p2 = k_mech / n_mech if n_mech else 0.0   # mechanism
    l1, u1 = wilson(k_base, n_base, z)
    l2, u2 = wilson(k_mech, n_mech, z)
    d = p2 - p1
    lo = d - math.sqrt((p2 - l2) ** 2 + (u1 - p1) ** 2)
    hi = d + math.sqrt((u2 - p2) ** 2 + (p1 - l1) ** 2)
    return (d, lo, hi)


def excludes_zero(lo: float, hi: float) -> bool:
    """True iff the difference interval (lo, hi) does NOT straddle 0 — i.e. a real effect.

    This is the honesty gate (DECISIONS D7): if the Newcombe interval includes 0, the two arms
    are statistically indistinguishable at this n and we report 'no clear effect,' never a win.
    """
    return lo > 0.0 or hi < 0.0
