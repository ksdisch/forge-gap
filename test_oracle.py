"""test_oracle.py — offline unit tests for the deterministic oracle + scenario.

No network, no model, no pytest — runnable with `uv run test_oracle.py` (same hand-rolled
style as verify.py). Proves the parts S2 must get exactly right BEFORE spending any API
calls:

  - the oracle grades correct / incorrect / non-numeric answers deterministically,
  - the scenario's ground truth matches its own records (140 + 18 = 158),
  - dispatch returns records for good lookups and honest errors for bad ones.

Exits non-zero if any check fails.
"""
from __future__ import annotations

import json
import sys

from agent import dispatch
from oracle import grade
from scenario import ORDER_SCENARIO

_failures: list[str] = []


def check(label: str, cond: bool) -> None:
    print(f"  [{'ok  ' if cond else 'FAIL'}] {label}")
    if not cond:
        _failures.append(label)


def test_oracle() -> None:
    print("oracle.grade — deterministic grading")
    ok, detail = grade(158, 158)
    check("exact int match -> correct", ok and detail["reason"] == "graded")
    check("float match -> correct", grade(158.0, 158)[0])
    check("wrong value -> incorrect", grade(159, 158)[0] is False)
    check("numeric string -> correct", grade("158", 158)[0])
    check("'$158' string -> correct", grade("$158", 158)[0])
    miss_ok, miss_detail = grade(None, 158)
    check("None submission -> incorrect", miss_ok is False)
    check("None submission -> reason no_numeric_answer", miss_detail["reason"] == "no_numeric_answer")
    check("bool rejected -> incorrect", grade(True, 158)[0] is False)
    check("non-numeric string -> incorrect", grade("abc", 158)[0] is False)


def test_ground_truth() -> None:
    print("scenario — ground truth matches the records")
    check("ORDER_SCENARIO.ground_truth == 158", ORDER_SCENARIO.ground_truth == 158)


def test_dispatch() -> None:
    print("agent.dispatch — offline tool machinery")
    reg = ORDER_SCENARIO.registry

    ok, result = dispatch("get_order", {"order_id": "ORD-204"}, reg)
    rec = json.loads(result) if ok else {}
    check("get_order(ORD-204) -> ok", ok)
    check("get_order(ORD-204) item_total_usd == 140", rec.get("item_total_usd") == 140)
    check("get_order(ORD-204) ship_zone == WEST", rec.get("ship_zone") == "WEST")

    ok2, result2 = dispatch("get_ship_rate", {"zone": "WEST"}, reg)
    rate = json.loads(result2) if ok2 else {}
    check("get_ship_rate(WEST) rate_usd == 18", ok2 and rate.get("rate_usd") == 18)

    bad_ok, bad_result = dispatch("get_order", {"order_id": "NOPE"}, reg)
    check("get_order(unknown) -> not ok", bad_ok is False)
    check("get_order(unknown) -> KeyError observation", bad_result.startswith("KeyError"))

    miss_ok, miss_result = dispatch("nonexistent_tool", {}, reg)
    check("unknown tool -> not ok", miss_ok is False)
    check("unknown tool -> 'unknown tool' observation", miss_result.startswith("unknown tool"))


def main() -> int:
    print("Offline tests: oracle + scenario + dispatch\n" + "-" * 44)
    test_oracle()
    print()
    test_ground_truth()
    print()
    test_dispatch()
    print("\n" + "-" * 44)
    if _failures:
        print(f"{len(_failures)} check(s) FAILED:")
        for f in _failures:
            print(f"  - {f}")
        return 1
    print("All checks passed — oracle grades, ground truth is consistent, dispatch is honest.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
