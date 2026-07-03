"""test_validation.py — offline unit tests for the S9 validate guardrail.

No network calls. Three layers:
  1. scenario.validate callable — does it recompute correctly from tool results?
  2. _validation_nudge_message — does it name components without stating the sum?
  3. agent.run(validate=True) integration — fake run where the model submits wrong then right.

Run: uv run test_validation.py
"""
from __future__ import annotations

import json

# ---------------------------------------------------------------------------
# 1. scenario.validate: the ORDER_SCENARIO recompute-from-evidence function
# ---------------------------------------------------------------------------

def _make_tool_msg(content: dict, tool_call_id: str = "c1") -> dict:
    return {"role": "tool", "tool_call_id": tool_call_id, "content": json.dumps(content)}


def test_validate_correct_submission():
    from scenario import ORDER_SCENARIO
    msgs = [
        _make_tool_msg({"customer": "Acme Co.", "item_total_usd": 140, "ship_zone": "WEST"}),
        _make_tool_msg({"zone": "WEST", "rate_usd": 18}, tool_call_id="c2"),
    ]
    consistent, evidence = ORDER_SCENARIO.validate(msgs, 158)
    assert consistent, "158 should be consistent with 140+18"
    assert evidence is None, "consistent submissions return evidence=None"


def test_validate_wrong_submission_missing_shipping():
    from scenario import ORDER_SCENARIO
    msgs = [
        _make_tool_msg({"customer": "Acme Co.", "item_total_usd": 140, "ship_zone": "WEST"}),
        _make_tool_msg({"zone": "WEST", "rate_usd": 18}, tool_call_id="c2"),
    ]
    consistent, evidence = ORDER_SCENARIO.validate(msgs, 140)
    assert not consistent, "140 is wrong when retrieved 140+18=158"
    assert evidence is not None, "inconsistent submissions return evidence dict"
    assert evidence["item_total_usd"] == 140
    assert evidence["rate_usd"] == 18
    assert evidence["expected"] == 158


def test_validate_partial_retrieval_no_rate():
    """If the model only retrieved the order but not the rate, can't recompute — accept."""
    from scenario import ORDER_SCENARIO
    msgs = [
        _make_tool_msg({"customer": "Acme Co.", "item_total_usd": 140, "ship_zone": "WEST"}),
    ]
    consistent, evidence = ORDER_SCENARIO.validate(msgs, 99999)
    assert consistent, "missing rate -> can't recompute -> accept (avoid false negative)"
    assert evidence is None


def test_validate_no_retrieval_at_all():
    from scenario import ORDER_SCENARIO
    msgs = [{"role": "user", "content": "What is the total?"}]
    consistent, evidence = ORDER_SCENARIO.validate(msgs, 0)
    assert consistent, "no tool results -> can't recompute -> accept"
    assert evidence is None


def test_validate_never_reads_ground_truth():
    """Validate function must only use tool result messages, NOT scenario.ground_truth."""
    from scenario import ORDER_SCENARIO, GROUND_TRUTH
    # Feed bogus retrieved data (wrong record values) — validator should recompute from THESE,
    # not from GROUND_TRUTH. So submitting 60 (50+10) is "consistent with wrong evidence."
    msgs = [
        _make_tool_msg({"item_total_usd": 50, "ship_zone": "EAST"}),
        _make_tool_msg({"zone": "EAST", "rate_usd": 10}, tool_call_id="c2"),
    ]
    consistent, evidence = ORDER_SCENARIO.validate(msgs, 60)
    assert consistent, "60 is consistent with wrong retrieved data (50+10) — validator doesn't check against ground truth"
    assert evidence is None

    # But 50 (item total only, shipping forgotten) IS inconsistent with THAT wrong data.
    consistent2, evidence2 = ORDER_SCENARIO.validate(msgs, 50)
    assert not consistent2
    assert evidence2 is not None
    assert evidence2["expected"] == 60  # recomputed from wrong-record data, not 158


def test_validate_with_validation_tool_result_in_messages():
    """The re-prompt appends a submit_answer tool result — it must not confuse the validator."""
    from scenario import ORDER_SCENARIO
    msgs = [
        _make_tool_msg({"customer": "Acme Co.", "item_total_usd": 140, "ship_zone": "WEST"}),
        _make_tool_msg({"zone": "WEST", "rate_usd": 18}, tool_call_id="c2"),
        # The validation re-prompt appends a synthetic tool result for submit_answer
        {"role": "tool", "tool_call_id": "c3",
         "content": "Answer 140 received but does not match retrieved data."},
    ]
    consistent, evidence = ORDER_SCENARIO.validate(msgs, 140)
    assert not consistent, "140 is still wrong; synthetic submit_answer tool result must not pollute evidence"


# ---------------------------------------------------------------------------
# 2. _validation_nudge_message: names components, NOT the sum
# ---------------------------------------------------------------------------

def test_nudge_names_components_not_sum():
    from agent import _validation_nudge_message
    evidence = {"item_total_usd": 140, "rate_usd": 18, "expected": 158}
    msg = _validation_nudge_message(140, evidence)
    assert "140" in msg, "re-prompt must mention the submitted value"
    assert "18" in msg, "re-prompt must mention the shipping rate component"
    # 158 (the sum) must NOT appear — the model must still do the addition itself.
    assert "158" not in msg, "re-prompt must NOT state the computed sum (D22 bright line)"
    assert "submit_answer" in msg.lower() or "resubmit" in msg.lower() or "call" in msg.lower()


def test_nudge_message_without_evidence():
    """validate returns evidence=None only when consistent; this path shouldn't be called,
    but the nudge message should still not crash with a generic evidence dict."""
    from agent import _validation_nudge_message
    evidence = {"item_total_usd": 75, "rate_usd": 12, "expected": 87}
    msg = _validation_nudge_message(75, evidence)
    assert "75" in msg
    assert "12" in msg
    assert "87" not in msg


# ---------------------------------------------------------------------------
# 3. agent.run integration: validate=True fires on wrong, accepts correct
#
# We drive agent.run() with a stubbed `chat` whose responses are plain
# types.SimpleNamespace objects (NOT MagicMock: `MagicMock(name="submit_answer")`
# silently swallows the `name` kwarg, so `.name` returns a child mock instead of
# the string — which breaks both the `== final_tool` check and JSON serialization).
# ---------------------------------------------------------------------------

from types import SimpleNamespace as _NS


def _call(cid, fname, args_str):
    """A stub tool_call: `.id`, `.function.name`, `.function.arguments`."""
    return _NS(id=cid, function=_NS(name=fname, arguments=args_str))


def _resp(tool_calls, *, content=None, finish_reason="tool_calls", usage=None):
    """A stub chat response shaped like the OpenAI SDK object agent.run() reads."""
    msg = _NS(content=content, tool_calls=tool_calls)
    return _NS(choices=[_NS(message=msg, finish_reason=finish_reason)], usage=usage)


def test_validate_toggle_off_accepts_wrong_answer():
    """With validate=False (default), a wrong submission (140) is accepted and graded False."""
    from unittest.mock import patch
    from agent import run
    from scenario import ORDER_SCENARIO

    # Model submits 140 (wrong) immediately; validate is off so it's accepted as final.
    resp = _resp([_call("c99", "submit_answer", '{"value": 140}')])
    with patch("agent.chat", return_value=resp):
        result = run(ORDER_SCENARIO, validate=False, out_path="/dev/null")

    assert result["stop"] == "submitted"
    assert result["submitted"] == 140
    assert result["correct"] is False
    assert result["validations"] == 0


def test_validate_toggle_on_reprompts_wrong_then_accepts_correct():
    """With validate=True, a wrong submission triggers a re-prompt; the corrected one is accepted."""
    from unittest.mock import patch
    from agent import run
    from scenario import ORDER_SCENARIO

    # Turn 0: get_order · Turn 1: get_ship_rate · Turn 2: submit 140 (wrong -> re-prompt) ·
    # Turn 3: submit 158 (correct -> accepted).
    side_effects = [
        _resp([_call("c1", "get_order", '{"order_id": "ORD-204"}')]),
        _resp([_call("c2", "get_ship_rate", '{"zone": "WEST"}')]),
        _resp([_call("c3", "submit_answer", '{"value": 140}')]),
        _resp([_call("c4", "submit_answer", '{"value": 158}')]),
    ]
    with patch("agent.chat", side_effect=side_effects):
        result = run(ORDER_SCENARIO, validate=True, max_steps=8, out_path="/dev/null")

    assert result["stop"] == "submitted"
    assert result["submitted"] == 158
    assert result["correct"] is True
    assert result["validations"] == 1, "exactly one validation re-prompt should have fired"


def test_validate_accepts_correct_without_repromotion():
    """With validate=True, a correct first submission (158) is accepted without any re-prompt."""
    from unittest.mock import patch
    from agent import run
    from scenario import ORDER_SCENARIO

    side_effects = [
        _resp([_call("c1", "get_order", '{"order_id": "ORD-204"}')]),
        _resp([_call("c2", "get_ship_rate", '{"zone": "WEST"}')]),
        _resp([_call("c3", "submit_answer", '{"value": 158}')]),
    ]
    with patch("agent.chat", side_effect=side_effects):
        result = run(ORDER_SCENARIO, validate=True, max_steps=8, out_path="/dev/null")

    assert result["stop"] == "submitted"
    assert result["submitted"] == 158
    assert result["correct"] is True
    assert result["validations"] == 0


def test_validate_accepts_when_evidence_incomplete():
    """If only the order is retrieved (no rate yet), validate can't recompute — accepts the answer."""
    from unittest.mock import patch
    from agent import run
    from scenario import ORDER_SCENARIO

    side_effects = [
        _resp([_call("c1", "get_order", '{"order_id": "ORD-204"}')]),
        # Skip get_ship_rate — submit without the rate lookup.
        _resp([_call("c2", "submit_answer", '{"value": 140}')]),
    ]
    with patch("agent.chat", side_effect=side_effects):
        result = run(ORDER_SCENARIO, validate=True, max_steps=8, out_path="/dev/null")

    # Missing rate evidence -> can't recompute -> no re-prompt -> accepted (but wrong per oracle).
    assert result["stop"] == "submitted"
    assert result["validations"] == 0, "no re-prompt when evidence is incomplete"
    assert result["correct"] is False  # oracle still catches it


# ---------------------------------------------------------------------------
# runner
# ---------------------------------------------------------------------------

def _run_all():
    tests = [
        test_validate_correct_submission,
        test_validate_wrong_submission_missing_shipping,
        test_validate_partial_retrieval_no_rate,
        test_validate_no_retrieval_at_all,
        test_validate_never_reads_ground_truth,
        test_validate_with_validation_tool_result_in_messages,
        test_nudge_names_components_not_sum,
        test_nudge_message_without_evidence,
        test_validate_toggle_off_accepts_wrong_answer,
        test_validate_toggle_on_reprompts_wrong_then_accepts_correct,
        test_validate_accepts_correct_without_repromotion,
        test_validate_accepts_when_evidence_incomplete,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception as exc:
            print(f"  FAIL  {t.__name__}: {exc}")
            failed += 1
    print(f"\n{passed + failed} tests — {passed} passed, {failed} failed")
    return failed


if __name__ == "__main__":
    raise SystemExit(_run_all())
