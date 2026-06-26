"""oracle.py — the deterministic oracle for forge-gap. NEVER an LLM judge.

Task success is measured against *known ground truth* — a value the scenario
computed in plain Python — not a model's opinion. This file is the "fixed ruler":
it takes whatever GLM submitted and a known-correct number, and returns a hard
True/False plus a reason.

Why this is defensible (the S2 teaching point):
  - Ground truth is derived by a SEPARATE Python path over the same records, so the
    thing being graded (GLM's tool-use) never influences its own grade — no circularity.
  - The comparison is mechanical equality, reproducible bit-for-bit.
  - An LLM judge here would be self-graded homework: you'd ask the same class of system
    that can fail the task to score it, importing its blind spots and sycophancy as
    noise/bias — a rubber ruler exactly where we need a fixed one to measure a
    completion-rate delta across arms.

Pure and synchronous: no network, no model call, trivially unit-testable (test_oracle.py).
"""
from __future__ import annotations


def _to_number(value) -> float | None:
    """Coerce a submitted value to float, or None if it isn't a real number.

    `bool` is rejected even though it's an int subclass: a True/False submission is
    a malformed answer, not the number 1/0. Strings are accepted leniently (strip a
    leading '$' and thousands separators) so a numerically-correct answer wrapped as
    text still grades as correct; anything non-numeric returns None.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip().lstrip("$").replace(",", ""))
        except ValueError:
            return None
    return None


def grade(submitted, expected, *, tol: float = 0.0) -> tuple[bool, dict]:
    """Grade `submitted` against the known-correct `expected`. Deterministic; no model.

    Returns (correct, detail). `tol` defaults to 0.0 — this is an EXACT oracle for the
    integer-USD scenario; the parameter just documents that and leaves room for a
    tolerance if a future scenario ever needs one.

    Any submission that isn't a real number (missing, malformed, non-numeric — the
    mechanical-failure cases) grades False with reason "no_numeric_answer", so S3's
    triage can tell *why* a run failed, not just that it did.
    """
    num = _to_number(submitted)
    if num is None:
        return False, {"reason": "no_numeric_answer", "submitted": submitted, "expected": expected}
    correct = abs(num - expected) <= tol
    return correct, {"reason": "graded", "submitted": num, "expected": expected, "tol": tol}
