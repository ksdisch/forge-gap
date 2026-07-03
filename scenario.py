"""scenario.py — the S2 lookup-then-compute scenario (order grand total).

The real task the whole project measures. GLM must chain two record lookups and
submit one computed number:

    get_order(order_id)   -> {customer, item_total_usd, ship_zone}
    get_ship_rate(zone)   -> {zone, rate_usd}        # zone comes from the order
    submit_answer(value)  -> terminal; the number the oracle grades

Grand total = item_total_usd + (shipping rate for the order's zone). The lookup is
*chained*: GLM can't fetch the rate until it has read `ship_zone` out of the order.
That chaining — threading a value from call 1 into call 2 — is where a multi-step
agent fails *mechanically* (wrong field, wrong zone, skipped step), which is exactly
the failure type S3 needs to find. The arithmetic is a single addition on purpose:
hard math would manufacture *cognitive* failures instead, the wrong kind for this thesis.

Ground truth is computed right here in plain Python (see GROUND_TRUTH), independent of
anything GLM does. `oracle.py` compares GLM's submitted value to it — never an LLM judge.

A `Scenario` bundles everything the loop in `agent.py` needs to drive one task, so later
sessions can push different scenarios / mechanism arms through the same engine.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass


# --- the Scenario bundle --------------------------------------------------
@dataclass(frozen=True)
class Scenario:
    """Everything agent.run() needs to drive one task, as immutable data.

    Bundling these (rather than passing six loose arguments) is what lets the
    reason->act->observe loop stay scenario-agnostic: the engine reads these
    fields; it never hardcodes a task.
    """
    name: str
    system_prompt: str
    task: str
    tools: list[dict]                 # OpenAI-style schemas GLM sees
    registry: dict[str, Callable]     # tool name -> python callable
    final_tool: str                   # terminal tool the loop stops on
    ground_truth: float               # the correct answer, known in advance
    validate: Callable | None = None  # S9 self-consistency check: (messages, submitted) ->
                                      # (consistent, evidence_or_None). Reads only the run's
                                      # tool results — never ground_truth. None = no check.


# --- the records (a tiny fixed "database") --------------------------------
# Small lookup tables so a *wrong* lookup is a real, observable failure: ask for
# an id/zone that isn't here and the tool raises -> an honest error observation,
# with no recovery (recovering from it is S4's job, not the scenario's).
ORDERS = {
    "ORD-204": {"customer": "Acme Co.", "item_total_usd": 140, "ship_zone": "WEST"},
    "ORD-318": {"customer": "Globex",   "item_total_usd": 75,  "ship_zone": "EAST"},
    "ORD-552": {"customer": "Initech",  "item_total_usd": 230, "ship_zone": "CENTRAL"},
}
SHIP_RATES = {
    "WEST":    {"zone": "WEST",    "rate_usd": 18},
    "EAST":    {"zone": "EAST",    "rate_usd": 12},
    "CENTRAL": {"zone": "CENTRAL", "rate_usd": 9},
}

# The single order this scenario asks about. N comes from running this SAME task
# many times (GLM is stochastic), not from varying the order — that's S4+.
TARGET_ORDER = "ORD-204"


# --- the two lookup tools -------------------------------------------------
def get_order(order_id: str) -> str:
    """Look up one order record. Returns a JSON string; raises if the id is unknown.

    `dispatch()` in agent.py catches the raise and feeds GLM an honest error
    string as the observation — that unknown-id path is a mechanical ACT failure.
    """
    rec = ORDERS.get(order_id)
    if rec is None:
        raise KeyError(f"no order {order_id!r}")
    return json.dumps(rec)


def get_ship_rate(zone: str) -> str:
    """Look up the shipping rate for a zone. Returns a JSON string; raises if unknown."""
    rec = SHIP_RATES.get(zone)
    if rec is None:
        raise KeyError(f"no shipping zone {zone!r}")
    return json.dumps(rec)


# --- tool schemas GLM sees ------------------------------------------------
GET_ORDER_TOOL = {
    "type": "function",
    "function": {
        "name": "get_order",
        "description": "Look up an order by its id. Returns customer, item_total_usd, and ship_zone.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "The order id, e.g. 'ORD-204'."},
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
                "zone": {"type": "string", "description": "The shipping zone, e.g. 'WEST'."},
            },
            "required": ["zone"],
        },
    },
}

SUBMIT_ANSWER_TOOL = {
    "type": "function",
    "function": {
        "name": "submit_answer",
        "description": (
            "Submit your final computed grand total in USD. Call this exactly once, "
            "when you have the answer. Calling it ends the task."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "value": {"type": "number", "description": "The final grand total in USD."},
            },
            "required": ["value"],
        },
    },
}


# --- prompts --------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are a careful operations assistant with access to tools. "
    "Use the tools to look up the data you need, compute the answer, "
    "then call submit_answer with the final number. Do not guess."
)

TASK = (
    f"Calculate the grand total for order {TARGET_ORDER} and submit it. "
    "The grand total is the order's item total plus the shipping rate for the "
    "order's shipping zone, in USD."
)


# --- ground truth, computed independently in plain Python -----------------
# The oracle's fixed ruler. It never runs GLM and never parses GLM's output;
# it derives the right answer straight from the records above.
_order = ORDERS[TARGET_ORDER]
GROUND_TRUTH = _order["item_total_usd"] + SHIP_RATES[_order["ship_zone"]]["rate_usd"]  # 140 + 18 = 158


# --- S9 validation function: recompute from the model's own retrieved evidence ----------------
# This is a SELF-CONSISTENCY check, not an answer check. It reads only the `messages` a run
# produced — specifically the tool results for get_order and get_ship_rate — and recomputes the
# total from those. It NEVER reads GROUND_TRUTH. That means it can be fooled by wrong-record
# retrieval (the model fetched the wrong order → it returns the self-consistent-but-wrong total
# and accepts it), but on this testbed retrieval is always correct, so all residual failures are
# pure arithmetic slips — exactly what this catches. Bright lines (D22): (1) never reads
# GROUND_TRUTH; (2) encoding "sum the retrieved line items" is narrow task knowledge, not the answer.
def _validate_order_total(
    messages: list[dict], submitted: float
) -> tuple[bool, dict | None]:
    """Recompute from tool results; return (consistent, evidence_or_None).

    consistent=True + evidence=None  → either matches, OR can't recompute (accept).
    consistent=False + evidence=dict → mismatch; evidence carries item_total_usd, rate_usd,
                                       expected for the re-prompt (D22).
    """
    item_total: float | None = None
    ship_rate: float | None = None
    for msg in messages:
        if msg.get("role") != "tool":
            continue
        try:
            data = json.loads(msg.get("content", "{}"))
        except (json.JSONDecodeError, TypeError):
            continue
        if "item_total_usd" in data and item_total is None:
            item_total = float(data["item_total_usd"])
        if "rate_usd" in data and ship_rate is None:
            ship_rate = float(data["rate_usd"])
    if item_total is None or ship_rate is None:
        return True, None  # can't recompute — accept (no false negative from missing evidence)
    try:
        sub_num = float(submitted)
    except (ValueError, TypeError):
        return True, None  # non-numeric submission — not our target; the oracle fails it instead
    expected = item_total + ship_rate
    if abs(sub_num - expected) < 0.01:
        return True, None
    return False, {"item_total_usd": item_total, "rate_usd": ship_rate, "expected": expected}


# --- the assembled scenario -----------------------------------------------
# Note: submit_answer is deliberately NOT in `registry`. It's the terminal tool —
# the loop intercepts it to capture GLM's answer and stop, so it's never dispatched.
ORDER_SCENARIO = Scenario(
    name="order_grand_total",
    system_prompt=SYSTEM_PROMPT,
    task=TASK,
    tools=[GET_ORDER_TOOL, GET_SHIP_RATE_TOOL, SUBMIT_ANSWER_TOOL],
    registry={"get_order": get_order, "get_ship_rate": get_ship_rate},
    final_tool="submit_answer",
    ground_truth=GROUND_TRUTH,
    validate=_validate_order_total,
)
