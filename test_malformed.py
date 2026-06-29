"""test_malformed.py — offline tests for the S6 malformed-call fault injector (reject-and-hint).

No network, no model, no pytest (`uv run test_malformed.py`). Proves the injector is honest BEFORE
we spend API calls measuring with it. The malformed fault is the failure **retry-nudge** fixes but
**error-recovery** cannot, so it must have two load-bearing properties this suite pins:

  1. PERMANENT, not transient — its `400 invalid_argument` error is classified non-retryable by
     `agent._is_retryable`, so error-recovery's harness-retry leaves it alone (the structural
     separation between the two guardrails — DECISIONS D19).
  2. STICKY — an armed tool rejects the *documented* parameter every time (a blind identical resend
     keeps failing); only a *corrected* call (the aliased parameter the hint names) clears it. Unlike
     the 503 (a fresh per-call coin-flip), so success requires real correction, not a lucky redraw.

Plus the usual honesty checks: arming rate ≈ `rate` across seeds, rate=0 leaves the task clean,
non-mutating, bad rate guarded.
"""
from __future__ import annotations

import json
import random
import sys

from agent import _is_retryable, dispatch, dispatch_with_recovery
from faults import MalformedCall, with_malformed_faults
from scenario import ORDER_SCENARIO

_failures: list[str] = []


def check(label: str, cond: bool) -> None:
    print(f"  [{'ok  ' if cond else 'FAIL'}] {label}")
    if not cond:
        _failures.append(label)


def _reg(rate: float, seed: int) -> dict:
    """The faulted registry for (rate, seed)."""
    return with_malformed_faults(ORDER_SCENARIO, rate=rate, seed=seed).registry


# get_order(order_id=...) -> corrected key 'id';  get_ship_rate(zone=...) -> corrected key 'region'.
CORRECT = {"get_order": ("order_id", "id", "ORD-204", 140),
           "get_ship_rate": ("zone", "region", "WEST", 18)}


def test_rate_extremes() -> None:
    print("with_malformed_faults — rate extremes")
    clean = _reg(0.0, seed=1)
    for tool, (adv, _corr, val, field) in CORRECT.items():
        ok, result = dispatch(tool, {adv: val}, clean)
        check(f"rate=0.0 {tool} returns the real record via '{adv}'",
              ok and (str(field) in result))

    armed = _reg(1.0, seed=1)
    for tool, (adv, corr, val, field) in CORRECT.items():
        ok, err = dispatch(tool, {adv: val}, armed)
        check(f"rate=1.0 {tool} rejects documented param '{adv}'", ok is False)
        check(f"rate=1.0 {tool} error is a MalformedCall/400", "400" in err and "MalformedCall" in err)
        check(f"rate=1.0 {tool} hint names the corrected param '{corr}'", repr(corr) in err or f"'{corr}'" in err)
        cok, cres = dispatch(tool, {corr: val}, armed)
        check(f"rate=1.0 {tool} CORRECTED call ('{corr}') succeeds", cok and (str(field) in cres))


def test_permanent_not_transient() -> None:
    print("malformed error — classified PERMANENT (error-recovery must ignore it)")
    armed = _reg(1.0, seed=3)
    ok, err = dispatch("get_order", {"order_id": "ORD-204"}, armed)
    check("malformed dispatch failed", ok is False)
    check("_is_retryable(malformed) is False", _is_retryable(err) is False)

    # error-recovery on the SAME armed tool: it must spend 0 recoveries and still fail (a blind
    # harness retry cannot fix a permanent, model-side error — the whole point of D19's separation).
    rok, rres, rec = dispatch_with_recovery("get_order", {"order_id": "ORD-204"}, armed,
                                            recover=True, max_recoveries=3)
    check("error-recovery does NOT rescue a malformed call (still fails)", rok is False)
    check("error-recovery spends 0 recoveries on a malformed call", rec == 0)

    # but a CORRECTED call goes straight through dispatch_with_recovery (sanity).
    cok, cres, crec = dispatch_with_recovery("get_order", {"id": "ORD-204"}, armed,
                                             recover=True, max_recoveries=3)
    check("corrected call succeeds through dispatch_with_recovery", cok and "140" in cres)
    check("corrected call spends 0 recoveries", crec == 0)


def test_sticky_resend_fails() -> None:
    print("stickiness — a blind identical resend keeps failing; only a corrected call clears it")
    armed = _reg(1.0, seed=5)
    outcomes = [dispatch("get_ship_rate", {"zone": "WEST"}, armed)[0] for _ in range(50)]
    check("50 identical uncorrected resends ALL fail (sticky, no lucky redraw)",
          all(ok is False for ok in outcomes))
    cok, _ = dispatch("get_ship_rate", {"region": "WEST"}, armed)
    check("the corrected resend succeeds", cok is True)


def test_determinism_and_rate() -> None:
    print("with_malformed_faults — determinism + arming rate across seeds")
    # Same (rate, seed) reproduces the same arming verdict per tool.
    a = dispatch("get_order", {"order_id": "ORD-204"}, _reg(0.5, seed=42))[0]
    b = dispatch("get_order", {"order_id": "ORD-204"}, _reg(0.5, seed=42))[0]
    check("same (rate, seed) -> identical arming verdict", a == b)

    # Arming is PER-SEED (not per-call), so the rate shows up across distinct seeds.
    n = 3000
    armed = sum(1 for s in range(n)
                if dispatch("get_order", {"order_id": "ORD-204"}, _reg(0.5, seed=s))[0] is False)
    frac = armed / n
    check(f"rate=0.5 arms ~50% of seeds (got {frac:.3f})", 0.45 <= frac <= 0.55)


def test_nonmutating() -> None:
    print("with_malformed_faults — non-mutating + preserves schema/ground truth")
    faulted = with_malformed_faults(ORDER_SCENARIO, rate=1.0, seed=1)
    ok, result = dispatch("get_order", {"order_id": "ORD-204"}, ORDER_SCENARIO.registry)
    check("original scenario untouched (still clean)", ok and "140" in result)
    check("faulted scenario keeps the same tool schemas", faulted.tools == ORDER_SCENARIO.tools)
    check("faulted scenario keeps ground truth", faulted.ground_truth == ORDER_SCENARIO.ground_truth)


def test_bad_rate() -> None:
    print("with_malformed_faults — guards invalid rate")
    raised = False
    try:
        with_malformed_faults(ORDER_SCENARIO, rate=-0.1, seed=1)
    except ValueError:
        raised = True
    check("rate<0 raises ValueError", raised)


def test_malformedcall_is_exception() -> None:
    print("MalformedCall — a real exception type")
    check("MalformedCall subclasses Exception", issubclass(MalformedCall, Exception))


def main() -> int:
    print("Offline tests: the S6 malformed-call fault injector\n" + "-" * 52)
    for t in (test_rate_extremes, test_permanent_not_transient, test_sticky_resend_fails,
              test_determinism_and_rate, test_nonmutating, test_bad_rate,
              test_malformedcall_is_exception):
        t()
        print()
    print("-" * 52)
    if _failures:
        print(f"{len(_failures)} check(s) FAILED:")
        for f in _failures:
            print(f"  - {f}")
        return 1
    print("All checks passed — malformed faults are permanent, sticky, correctable, and honest.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
