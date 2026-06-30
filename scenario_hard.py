"""scenario_hard.py — the S7 "hard task v1" for the natural-gap hunt (DECISIONS D20).

S3–S6 measured *injected* gaps because GLM-4.6 aces the S2 task (`scenario.py`) on its own.
S7 drops injection and instead **hardens the task itself** until GLM fails on its *own*
mechanical merits. Two levers, both producing the on-thesis *mechanical* failure class
(wrong field threaded, wrong record, skipped link) — never *cognitive* (hard math), which
the S2 design deliberately avoids:

  Lever 1 — a LONGER CHAIN (4 chained lookups instead of 2):
      find_orders(customer)          -> [{order_id, ship_zone}, ...]   # which order?
      get_order(order_id)            -> {customer, item_total_usd, ship_zone}
      get_ship_rate(zone)            -> {rate_usd}        # zone threaded from the order
      get_customer_discount(customer)-> {discount_usd}    # customer threaded from the order
      submit_answer(value)           -> terminal
      grand_total = item_total + shipping_rate - customer_discount

  Lever 2 — a BIGGER, CONFUSABLE record set: ~15 orders with look-alike ids
      (ORD-204 / ORD-240 / ORD-024 …) and *several orders per customer in different zones*.
      The task names the order **by description** ("the Globex order shipping to EAST"),
      so the model must DISAMBIGUATE — pick the one order matching the requested zone.

Where this can fail mechanically (exactly what the pilot's triage looks for):
  - find_orders with the wrong customer            -> KeyError (a tool ERROR)
  - pick the wrong order_id from the list           -> wrong item_total/zone -> WRONG ANSWER, no error
  - thread the wrong zone / forget the discount step -> WRONG ANSWER, no error
  - get the chain right                              -> 158-style correct submit

Ground truth is computed right here in plain Python (see GROUND_TRUTH), independent of GLM —
`oracle.py` grades GLM's submitted value against it, never an LLM judge. The frozen
`ORDER_SCENARIO` in `scenario.py` is left untouched (the shipped S5 figure + its tests depend
on it); this is a *new* Scenario pushed through the same engine.

Run a clean baseline pilot:  uv run pilot.py
"""
from __future__ import annotations

import json

from scenario import SUBMIT_ANSWER_TOOL, Scenario


# --- the records (a bigger, deliberately confusable "database") -----------
# Look-alike ids (204/240/024 …) and several orders per customer in different zones, so a
# *wrong pick* is a real, observable failure that throws no error — it just yields the wrong
# number. Small enough to hand-verify the ground truth; varied enough to force disambiguation.
ORDERS = {
    "ORD-204": {"customer": "Globex",   "item_total_usd": 140, "ship_zone": "WEST"},
    "ORD-240": {"customer": "Globex",   "item_total_usd": 90,  "ship_zone": "EAST"},     # <- target
    "ORD-024": {"customer": "Globex",   "item_total_usd": 310, "ship_zone": "CENTRAL"},
    "ORD-402": {"customer": "Acme Co.",  "item_total_usd": 75,  "ship_zone": "EAST"},
    "ORD-420": {"customer": "Acme Co.",  "item_total_usd": 220, "ship_zone": "WEST"},
    "ORD-318": {"customer": "Initech",  "item_total_usd": 230, "ship_zone": "CENTRAL"},
    "ORD-381": {"customer": "Initech",  "item_total_usd": 60,  "ship_zone": "EAST"},
    "ORD-552": {"customer": "Hooli",    "item_total_usd": 175, "ship_zone": "WEST"},
    "ORD-525": {"customer": "Hooli",    "item_total_usd": 410, "ship_zone": "SOUTH"},
    "ORD-660": {"customer": "Umbrella", "item_total_usd": 50,  "ship_zone": "NORTH"},
    "ORD-606": {"customer": "Umbrella", "item_total_usd": 130, "ship_zone": "EAST"},
    "ORD-713": {"customer": "Stark",    "item_total_usd": 95,  "ship_zone": "CENTRAL"},
    "ORD-731": {"customer": "Stark",    "item_total_usd": 280, "ship_zone": "WEST"},
    "ORD-849": {"customer": "Wayne",    "item_total_usd": 160, "ship_zone": "EAST"},
    "ORD-948": {"customer": "Wayne",    "item_total_usd": 200, "ship_zone": "SOUTH"},
}
SHIP_RATES = {"WEST": 18, "EAST": 12, "CENTRAL": 9, "NORTH": 22, "SOUTH": 15}
CUSTOMER_DISCOUNTS = {
    "Globex": 20, "Acme Co.": 5, "Initech": 15, "Hooli": 30,
    "Umbrella": 0, "Stark": 25, "Wayne": 10,
}

# The order is named by DESCRIPTION, not id: the (customer, zone) the task asks about. The model
# must use find_orders + the zone to recover the id itself — that disambiguation is lever 2's bite.
TARGET_CUSTOMER = "Globex"
TARGET_ZONE = "EAST"


# --- the four lookup tools (each raises on an unknown key -> an honest tool error) ---
def find_orders(customer: str) -> str:
    """List a customer's orders as [{order_id, ship_zone}, ...]. Raises if the customer is unknown.

    Deliberately returns ONLY id + zone (not the item total), so the model still has to call
    get_order for the amount — that keeps the chain long. Several rows per customer is the point:
    the model must pick the row whose zone matches the task."""
    rows = [{"order_id": oid, "ship_zone": o["ship_zone"]}
            for oid, o in ORDERS.items() if o["customer"] == customer]
    if not rows:
        raise KeyError(f"no orders for customer {customer!r}")
    return json.dumps(rows)


def get_order(order_id: str) -> str:
    """Look up one order's details. Returns a JSON string; raises if the id is unknown."""
    rec = ORDERS.get(order_id)
    if rec is None:
        raise KeyError(f"no order {order_id!r}")
    return json.dumps(rec)


def get_ship_rate(zone: str) -> str:
    """Look up the shipping rate (USD) for a zone. Returns a JSON string; raises if unknown."""
    rate = SHIP_RATES.get(zone)
    if rate is None:
        raise KeyError(f"no shipping zone {zone!r}")
    return json.dumps({"zone": zone, "rate_usd": rate})


def get_customer_discount(customer: str) -> str:
    """Look up a customer's account discount (USD). Returns a JSON string; raises if unknown."""
    disc = CUSTOMER_DISCOUNTS.get(customer)
    if disc is None:
        raise KeyError(f"no customer {customer!r}")
    return json.dumps({"customer": customer, "discount_usd": disc})


# --- tool schemas GLM sees ------------------------------------------------
FIND_ORDERS_TOOL = {
    "type": "function",
    "function": {
        "name": "find_orders",
        "description": (
            "List a customer's orders (each with its order_id and shipping zone). "
            "Use this to find the right order id when you only know the customer."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "customer": {"type": "string", "description": "The customer name, e.g. 'Globex'."},
            },
            "required": ["customer"],
        },
    },
}

GET_ORDER_TOOL = {
    "type": "function",
    "function": {
        "name": "get_order",
        "description": "Look up an order by its id. Returns customer, item_total_usd, and ship_zone.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "The order id, e.g. 'ORD-240'."},
            },
            "required": ["order_id"],
        },
    },
}

GET_SHIP_RATE_TOOL = {
    "type": "function",
    "function": {
        "name": "get_ship_rate",
        "description": "Look up the shipping rate (USD) for a shipping zone.",
        "parameters": {
            "type": "object",
            "properties": {
                "zone": {"type": "string", "description": "The shipping zone, e.g. 'EAST'."},
            },
            "required": ["zone"],
        },
    },
}

GET_CUSTOMER_DISCOUNT_TOOL = {
    "type": "function",
    "function": {
        "name": "get_customer_discount",
        "description": "Look up a customer's account discount (USD), subtracted from the grand total.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer": {"type": "string", "description": "The customer name, e.g. 'Globex'."},
            },
            "required": ["customer"],
        },
    },
}


# --- prompts --------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are a careful operations assistant with access to tools. "
    "Use the tools to find the right order, look up the data you need, compute the answer, "
    "then call submit_answer with the final number. Do not guess."
)

TASK = (
    f"Calculate the grand total for the {TARGET_CUSTOMER} order shipping to the {TARGET_ZONE} "
    "zone, and submit it. The grand total is the order's item total, plus the shipping rate for "
    "the order's shipping zone, minus the customer's account discount, in USD."
)


# --- ground truth, computed independently in plain Python -----------------
# The oracle's fixed ruler: it derives the right answer straight from the records, never from GLM.
# Find the one order matching (TARGET_CUSTOMER, TARGET_ZONE), then item_total + rate - discount.
_target_id = next(
    oid for oid, o in ORDERS.items()
    if o["customer"] == TARGET_CUSTOMER and o["ship_zone"] == TARGET_ZONE
)
_o = ORDERS[_target_id]
GROUND_TRUTH = (
    _o["item_total_usd"]
    + SHIP_RATES[_o["ship_zone"]]
    - CUSTOMER_DISCOUNTS[_o["customer"]]
)  # ORD-240: 90 + 12 - 20 = 82


# --- the assembled hard scenario ------------------------------------------
# submit_answer is intentionally NOT in `registry` — it's the terminal tool the loop intercepts.
HARD_SCENARIO = Scenario(
    name="order_grand_total_hard",
    system_prompt=SYSTEM_PROMPT,
    task=TASK,
    tools=[FIND_ORDERS_TOOL, GET_ORDER_TOOL, GET_SHIP_RATE_TOOL,
           GET_CUSTOMER_DISCOUNT_TOOL, SUBMIT_ANSWER_TOOL],
    registry={
        "find_orders": find_orders,
        "get_order": get_order,
        "get_ship_rate": get_ship_rate,
        "get_customer_discount": get_customer_discount,
    },
    final_tool="submit_answer",
    ground_truth=GROUND_TRUTH,
)


# ===== HARD TASK V2 — the S7 escalation (DECISIONS D20) ===================
# v1 (above) scored 8/8 — GLM aced it. v2 pushes difficulty up ONCE more, then we stop (the
# bounded-escalation rule): a DEEPER chain (a 5th lookup — per-zone tax — so the total is a
# four-term sum/difference; the math stays trivial) through a BIGGER, more-confusable record set
# (~25 orders, 4–5 per customer) with a NEAR-DUPLICATE customer name as a distractor ("Globex" vs
# "Globex Labs", each with its OWN EAST order). Still on-thesis: every added difficulty is a place to
# thread/pick the WRONG value, not to out-think hard arithmetic. The four schemas above are reused
# (same tool API); only the backing records change, plus one new tool (get_zone_tax).

ORDERS_V2 = {
    # Globex (the target customer) — 5 orders, exactly ONE in EAST (the unique target).
    "ORD-310": {"customer": "Globex",      "item_total_usd": 200, "ship_zone": "WEST"},
    "ORD-301": {"customer": "Globex",      "item_total_usd": 120, "ship_zone": "EAST"},   # <- target
    "ORD-130": {"customer": "Globex",      "item_total_usd": 340, "ship_zone": "CENTRAL"},
    "ORD-103": {"customer": "Globex",      "item_total_usd": 75,  "ship_zone": "NORTH"},
    "ORD-013": {"customer": "Globex",      "item_total_usd": 260, "ship_zone": "SOUTH"},
    # Globex Labs — the near-duplicate-name DISTRACTOR; it ALSO has an EAST order (ORD-311).
    "ORD-311": {"customer": "Globex Labs", "item_total_usd": 180, "ship_zone": "EAST"},
    "ORD-131": {"customer": "Globex Labs", "item_total_usd": 95,  "ship_zone": "WEST"},
    "ORD-113": {"customer": "Globex Labs", "item_total_usd": 410, "ship_zone": "CENTRAL"},
    "ORD-133": {"customer": "Globex Labs", "item_total_usd": 150, "ship_zone": "SOUTH"},
    # Initech
    "ORD-220": {"customer": "Initech",     "item_total_usd": 230, "ship_zone": "CENTRAL"},
    "ORD-202": {"customer": "Initech",     "item_total_usd": 60,  "ship_zone": "EAST"},
    "ORD-022": {"customer": "Initech",     "item_total_usd": 130, "ship_zone": "WEST"},
    "ORD-200": {"customer": "Initech",     "item_total_usd": 300, "ship_zone": "NORTH"},
    # Hooli
    "ORD-450": {"customer": "Hooli",       "item_total_usd": 175, "ship_zone": "WEST"},
    "ORD-405": {"customer": "Hooli",       "item_total_usd": 410, "ship_zone": "SOUTH"},
    "ORD-540": {"customer": "Hooli",       "item_total_usd": 90,  "ship_zone": "EAST"},
    "ORD-504": {"customer": "Hooli",       "item_total_usd": 220, "ship_zone": "CENTRAL"},
    # Umbrella
    "ORD-660": {"customer": "Umbrella",    "item_total_usd": 50,  "ship_zone": "NORTH"},
    "ORD-606": {"customer": "Umbrella",    "item_total_usd": 130, "ship_zone": "EAST"},
    "ORD-066": {"customer": "Umbrella",    "item_total_usd": 280, "ship_zone": "WEST"},
    "ORD-600": {"customer": "Umbrella",    "item_total_usd": 160, "ship_zone": "SOUTH"},
    # Stark
    "ORD-715": {"customer": "Stark",       "item_total_usd": 95,  "ship_zone": "CENTRAL"},
    "ORD-751": {"customer": "Stark",       "item_total_usd": 280, "ship_zone": "WEST"},
    "ORD-175": {"customer": "Stark",       "item_total_usd": 200, "ship_zone": "EAST"},
    "ORD-157": {"customer": "Stark",       "item_total_usd": 175, "ship_zone": "SOUTH"},
}
SHIP_RATES_V2 = {"WEST": 18, "EAST": 12, "CENTRAL": 9, "NORTH": 22, "SOUTH": 15}
ZONE_TAX_V2 = {"WEST": 8, "EAST": 5, "CENTRAL": 4, "NORTH": 11, "SOUTH": 7}   # the new 5th-lookup term
CUSTOMER_DISCOUNTS_V2 = {
    "Globex": 20, "Globex Labs": 35, "Initech": 15, "Hooli": 30, "Umbrella": 0, "Stark": 25,
}

TARGET_CUSTOMER_V2 = "Globex"
TARGET_ZONE_V2 = "EAST"


def find_orders_v2(customer: str) -> str:
    """v2 find_orders — same contract as v1, over the bigger v2 record set. Exact-match on customer,
    so 'Globex' does NOT return the 'Globex Labs' rows (conflating them is a real wrong-answer trap)."""
    rows = [{"order_id": oid, "ship_zone": o["ship_zone"]}
            for oid, o in ORDERS_V2.items() if o["customer"] == customer]
    if not rows:
        raise KeyError(f"no orders for customer {customer!r}")
    return json.dumps(rows)


def get_order_v2(order_id: str) -> str:
    rec = ORDERS_V2.get(order_id)
    if rec is None:
        raise KeyError(f"no order {order_id!r}")
    return json.dumps(rec)


def get_ship_rate_v2(zone: str) -> str:
    rate = SHIP_RATES_V2.get(zone)
    if rate is None:
        raise KeyError(f"no shipping zone {zone!r}")
    return json.dumps({"zone": zone, "rate_usd": rate})


def get_zone_tax_v2(zone: str) -> str:
    """The NEW 5th lookup: a per-zone tax added to the grand total (the deeper-chain lever)."""
    tax = ZONE_TAX_V2.get(zone)
    if tax is None:
        raise KeyError(f"no tax for zone {zone!r}")
    return json.dumps({"zone": zone, "tax_usd": tax})


def get_customer_discount_v2(customer: str) -> str:
    disc = CUSTOMER_DISCOUNTS_V2.get(customer)
    if disc is None:
        raise KeyError(f"no customer {customer!r}")
    return json.dumps({"customer": customer, "discount_usd": disc})


GET_ZONE_TAX_TOOL = {
    "type": "function",
    "function": {
        "name": "get_zone_tax",
        "description": "Look up the tax (USD) for a shipping zone; it is added to the grand total.",
        "parameters": {
            "type": "object",
            "properties": {
                "zone": {"type": "string", "description": "The shipping zone, e.g. 'EAST'."},
            },
            "required": ["zone"],
        },
    },
}

TASK_V2 = (
    f"Calculate the grand total for the {TARGET_CUSTOMER_V2} order shipping to the {TARGET_ZONE_V2} "
    "zone, and submit it. The grand total is the order's item total, plus the shipping rate for the "
    "order's shipping zone, plus the zone's tax, minus the customer's account discount, in USD."
)

# Ground truth, computed independently: the unique (Globex, EAST) order, then item + ship + tax - disc.
_target_id_v2 = next(
    oid for oid, o in ORDERS_V2.items()
    if o["customer"] == TARGET_CUSTOMER_V2 and o["ship_zone"] == TARGET_ZONE_V2
)
_o2 = ORDERS_V2[_target_id_v2]
GROUND_TRUTH_V2 = (
    _o2["item_total_usd"]
    + SHIP_RATES_V2[_o2["ship_zone"]]
    + ZONE_TAX_V2[_o2["ship_zone"]]
    - CUSTOMER_DISCOUNTS_V2[_o2["customer"]]
)  # ORD-301: 120 + 12 + 5 - 20 = 117

HARD_SCENARIO_V2 = Scenario(
    name="order_grand_total_hard_v2",
    system_prompt=SYSTEM_PROMPT,
    task=TASK_V2,
    tools=[FIND_ORDERS_TOOL, GET_ORDER_TOOL, GET_SHIP_RATE_TOOL, GET_ZONE_TAX_TOOL,
           GET_CUSTOMER_DISCOUNT_TOOL, SUBMIT_ANSWER_TOOL],
    registry={
        "find_orders": find_orders_v2,
        "get_order": get_order_v2,
        "get_ship_rate": get_ship_rate_v2,
        "get_zone_tax": get_zone_tax_v2,
        "get_customer_discount": get_customer_discount_v2,
    },
    final_tool="submit_answer",
    ground_truth=GROUND_TRUTH_V2,
)
