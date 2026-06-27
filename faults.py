"""faults.py — a deterministic mechanical-fault injector (the S3-pivot foundation).

S3 found GLM-4.6 aces the clean task (20/20), so there's no *natural* gap to measure
(DECISIONS D12). To build and measure the recovery guardrails we need a *recoverable* failure
that happens on demand — so this injects one: it wraps a Scenario's lookup tools so each call
has probability `rate` of raising a **transient 503-style error** instead of returning the
record. The bare loop (`agent.dispatch`) catches that error and feeds it back as the observation
— exactly the mechanical failure retry-nudge / error-recovery are built to recover from.

Why a transient 503 (and not a malformed result or a wrong record)? It maps *exactly* onto the
planned guardrails: the recovery is "the call failed — try again." A malformed-JSON result tests
parsing-recovery (fuzzier), and a wrong record tests *validation* (a different guardrail entirely,
since no error fires). We can add those later; the 503 is the clean match for retry/recovery.

Design notes:
  - **Non-mutating:** `with_faults` returns a NEW Scenario (via `dataclasses.replace`); the
    original ORDER_SCENARIO is never touched, so the clean baseline stays clean.
  - **Deterministic:** a per-scenario `random.Random(seed)` drives the fault draws, so the same
    seed reproduces the same fault *sequence*. (The sequence is reproducible; which tool call
    lands on which draw still depends on the stochastic agent — that's honest, and part of where
    N comes from.) The runner passes seed=trial_index so every trial is reproducible yet distinct.
  - **rate=0.0 ≡ the clean task** — a useful "injection off" control.
  - The terminal tool (`submit_answer`) isn't in the registry, so it's never faulted.
"""
from __future__ import annotations

import functools
import random
from dataclasses import replace

from scenario import ORDER_SCENARIO, Scenario


class ToolUnavailable(Exception):
    """A transient, retryable tool failure (503-style) — the injected mechanical fault."""


def with_faults(scenario: Scenario = ORDER_SCENARIO, *, rate: float, seed: int) -> Scenario:
    """Return a copy of `scenario` whose lookup tools fail transiently at probability `rate`.

    Each wrapped-tool call draws from a seeded RNG: with probability `rate` it raises
    `ToolUnavailable` (a 503-style transient error); otherwise it runs the real tool and returns
    the real record. `seed` makes the fault sequence reproducible. `rate=0.0` reproduces the
    original behavior exactly.
    """
    if not 0.0 <= rate <= 1.0:
        raise ValueError(f"rate must be in [0.0, 1.0], got {rate!r}")
    rng = random.Random(seed)

    def wrap(tool_name, fn):
        @functools.wraps(fn)
        def faulty(**kwargs):
            if rng.random() < rate:
                raise ToolUnavailable(f"503 {tool_name} temporarily unavailable, retry")
            return fn(**kwargs)
        return faulty

    faulty_registry = {name: wrap(name, fn) for name, fn in scenario.registry.items()}
    return replace(scenario, name=f"{scenario.name}__faults{rate}", registry=faulty_registry)
