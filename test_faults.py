"""test_faults.py — offline unit tests for the deterministic fault injector.

No network, no model, no pytest (`uv run test_faults.py`). Proves the injector is honest BEFORE
we spend API calls measuring with it: it faults at the rate we ask, the same seed reproduces the
same fault sequence, rate=0 leaves the task clean, it returns the real record when it doesn't
fault, it never mutates the original scenario, and the injected fault flows through
`agent.dispatch` as a recoverable (False, error) observation.
"""
from __future__ import annotations

import json
import sys

from agent import dispatch
from faults import ToolUnavailable, with_faults
from scenario import ORDER_SCENARIO

_failures: list[str] = []


def check(label: str, cond: bool) -> None:
    print(f"  [{'ok  ' if cond else 'FAIL'}] {label}")
    if not cond:
        _failures.append(label)


def _fault_seq(scenario, n):
    """Call get_order n times; return a list of True (faulted) / False (returned a record)."""
    tool = scenario.registry["get_order"]
    seq = []
    for _ in range(n):
        try:
            tool(order_id="ORD-204")
            seq.append(False)
        except ToolUnavailable:
            seq.append(True)
    return seq


def test_rate_extremes() -> None:
    print("with_faults — rate extremes")
    clean = with_faults(ORDER_SCENARIO, rate=0.0, seed=1)
    check("rate=0.0 never faults", not any(_fault_seq(clean, 100)))
    ok, result = dispatch("get_order", {"order_id": "ORD-204"}, clean.registry)
    check("rate=0.0 returns the real record", ok and json.loads(result)["item_total_usd"] == 140)

    always = with_faults(ORDER_SCENARIO, rate=1.0, seed=1)
    check("rate=1.0 always faults", all(_fault_seq(always, 100)))


def test_determinism_and_rate() -> None:
    print("with_faults — determinism + observed rate")
    a = _fault_seq(with_faults(ORDER_SCENARIO, rate=0.5, seed=42), 200)
    b = _fault_seq(with_faults(ORDER_SCENARIO, rate=0.5, seed=42), 200)
    check("same seed -> identical fault sequence", a == b)

    c = _fault_seq(with_faults(ORDER_SCENARIO, rate=0.5, seed=7), 200)
    check("different seed -> different sequence", a != c)

    n = 4000
    faults = sum(_fault_seq(with_faults(ORDER_SCENARIO, rate=0.5, seed=123), n))
    frac = faults / n
    check(f"rate=0.5 observed ~0.5 (got {frac:.3f})", 0.45 <= frac <= 0.55)


def test_nonmutating_and_dispatch() -> None:
    print("with_faults — non-mutating + flows through dispatch")
    with_faults(ORDER_SCENARIO, rate=1.0, seed=1)  # wrapping must not touch the original
    ok, result = dispatch("get_order", {"order_id": "ORD-204"}, ORDER_SCENARIO.registry)
    check("original scenario untouched (still clean)", ok and "140" in result)

    always = with_faults(ORDER_SCENARIO, rate=1.0, seed=1)
    fok, ferr = dispatch("get_order", {"order_id": "ORD-204"}, always.registry)
    check("injected fault -> dispatch ok=False", fok is False)
    check("injected fault -> ToolUnavailable observation", ferr.startswith("ToolUnavailable"))

    check("faulted scenario keeps the same tool schemas", always.tools == ORDER_SCENARIO.tools)
    check("faulted scenario keeps ground truth", always.ground_truth == ORDER_SCENARIO.ground_truth)


def test_bad_rate() -> None:
    print("with_faults — guards invalid rate")
    raised = False
    try:
        with_faults(ORDER_SCENARIO, rate=1.5, seed=1)
    except ValueError:
        raised = True
    check("rate>1 raises ValueError", raised)


def main() -> int:
    print("Offline tests: the deterministic fault injector\n" + "-" * 47)
    test_rate_extremes()
    print()
    test_determinism_and_rate()
    print()
    test_nonmutating_and_dispatch()
    print()
    test_bad_rate()
    print("\n" + "-" * 47)
    if _failures:
        print(f"{len(_failures)} check(s) FAILED:")
        for f in _failures:
            print(f"  - {f}")
        return 1
    print("All checks passed — injection is deterministic, rate-accurate, non-mutating, recoverable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
