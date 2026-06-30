"""test_scenario_hard.py — offline unit tests for the S7 hardened scenario (DECISIONS D20).

No network, no model, no pytest — runnable with `uv run test_scenario_hard.py` (same hand-rolled
style as test_oracle.py). Proves the parts the natural-gap pilot must get exactly right BEFORE
spending any API calls:

  - the ground truth matches its own records and is the (Globex, EAST) order = 90 + 12 - 20 = 82,
  - the target is UNIQUE (exactly one Globex order ships to EAST), so disambiguation has one answer,
  - every lookup tool returns the right record and raises an honest error on an unknown key,
  - walking the full chain through the tools reproduces the ground truth,
  - the Scenario is wired correctly (4 lookup tools in the registry; submit_answer terminal-only).

Exits non-zero if any check fails.
"""
from __future__ import annotations

import json
import sys

from agent import dispatch
from scenario_hard import (
    CUSTOMER_DISCOUNTS,
    GROUND_TRUTH,
    HARD_SCENARIO,
    ORDERS,
    SHIP_RATES,
    TARGET_CUSTOMER,
    TARGET_ZONE,
)

_failures: list[str] = []


def check(label: str, cond: bool) -> None:
    print(f"  [{'ok  ' if cond else 'FAIL'}] {label}")
    if not cond:
        _failures.append(label)


def test_ground_truth() -> None:
    print("scenario_hard — ground truth matches the records")
    check("GROUND_TRUTH == 82", GROUND_TRUTH == 82)
    matches = [oid for oid, o in ORDERS.items()
               if o["customer"] == TARGET_CUSTOMER and o["ship_zone"] == TARGET_ZONE]
    check("exactly ONE (Globex, EAST) order -> unambiguous target", len(matches) == 1)
    check("the target order is ORD-240", matches == ["ORD-240"])
    o = ORDERS["ORD-240"]
    recomputed = o["item_total_usd"] + SHIP_RATES[o["ship_zone"]] - CUSTOMER_DISCOUNTS[o["customer"]]
    check("90 + 12 - 20 == GROUND_TRUTH", recomputed == GROUND_TRUTH)


def test_tools() -> None:
    print("scenario_hard — the four lookup tools (via the real dispatch machinery)")
    reg = HARD_SCENARIO.registry

    ok, result = dispatch("find_orders", {"customer": "Globex"}, reg)
    rows = json.loads(result) if ok else []
    check("find_orders(Globex) -> ok", ok)
    check("find_orders(Globex) -> 3 orders", len(rows) == 3)
    check("find_orders(Globex) includes ORD-240/EAST",
          any(r["order_id"] == "ORD-240" and r["ship_zone"] == "EAST" for r in rows))

    bad_ok, bad_result = dispatch("find_orders", {"customer": "Nobody"}, reg)
    check("find_orders(unknown) -> not ok", bad_ok is False)
    check("find_orders(unknown) -> KeyError observation", bad_result.startswith("KeyError"))

    ok2, result2 = dispatch("get_order", {"order_id": "ORD-240"}, reg)
    rec = json.loads(result2) if ok2 else {}
    check("get_order(ORD-240) item_total_usd == 90", rec.get("item_total_usd") == 90)
    check("get_order(ORD-240) ship_zone == EAST", rec.get("ship_zone") == "EAST")
    check("get_order(ORD-240) customer == Globex", rec.get("customer") == "Globex")

    bad2_ok, bad2_result = dispatch("get_order", {"order_id": "NOPE"}, reg)
    check("get_order(unknown) -> KeyError observation", bad2_ok is False and bad2_result.startswith("KeyError"))

    ok3, result3 = dispatch("get_ship_rate", {"zone": "EAST"}, reg)
    check("get_ship_rate(EAST) rate_usd == 12", ok3 and json.loads(result3).get("rate_usd") == 12)

    ok4, result4 = dispatch("get_customer_discount", {"customer": "Globex"}, reg)
    check("get_customer_discount(Globex) discount_usd == 20", ok4 and json.loads(result4).get("discount_usd") == 20)

    bad3_ok, _ = dispatch("get_ship_rate", {"zone": "MARS"}, reg)
    check("get_ship_rate(unknown) -> not ok", bad3_ok is False)


def test_full_chain() -> None:
    print("scenario_hard — walking the whole chain through the tools reproduces ground truth")
    reg = HARD_SCENARIO.registry
    # 1) find the (Globex, EAST) order id   2) get its total   3) ship rate   4) discount
    rows = json.loads(dispatch("find_orders", {"customer": TARGET_CUSTOMER}, reg)[1])
    picked = next(r["order_id"] for r in rows if r["ship_zone"] == TARGET_ZONE)
    order = json.loads(dispatch("get_order", {"order_id": picked}, reg)[1])
    rate = json.loads(dispatch("get_ship_rate", {"zone": order["ship_zone"]}, reg)[1])["rate_usd"]
    disc = json.loads(dispatch("get_customer_discount", {"customer": order["customer"]}, reg)[1])["discount_usd"]
    total = order["item_total_usd"] + rate - disc
    check("chained tool walk -> 82", total == GROUND_TRUTH)


def test_wiring() -> None:
    print("scenario_hard — the Scenario is assembled correctly")
    check("final_tool == submit_answer", HARD_SCENARIO.final_tool == "submit_answer")
    check("submit_answer is NOT in the registry (terminal-only)",
          "submit_answer" not in HARD_SCENARIO.registry)
    check("registry has the 4 lookup tools",
          set(HARD_SCENARIO.registry) == {"find_orders", "get_order", "get_ship_rate", "get_customer_discount"})
    tool_names = {t["function"]["name"] for t in HARD_SCENARIO.tools}
    check("tools schema includes submit_answer", "submit_answer" in tool_names)
    check("tools schema exposes all 5 tools to GLM", len(tool_names) == 5)
    check("ground_truth on the scenario == 82", HARD_SCENARIO.ground_truth == 82)


def main() -> int:
    print("Offline tests: hardened scenario (S7)\n" + "-" * 44)
    for t in (test_ground_truth, test_tools, test_full_chain, test_wiring):
        t()
        print()
    print("-" * 44)
    if _failures:
        print(f"{len(_failures)} check(s) FAILED:")
        for f in _failures:
            print(f"  - {f}")
        return 1
    print("All checks passed — hard scenario ground truth, tools, chain, and wiring are sound.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
