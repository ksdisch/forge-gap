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

S6 adds a *second* fault — `with_malformed_faults` — the failure that **retry-nudge** fixes but
**error-recovery** cannot (DECISIONS D19). Where the 503 is a flaky *service* (the call is fine, the
tool hiccups), a malformed-call fault is a bad *call*: an "armed" tool rejects the documented
parameter (`order_id`/`zone`) with an informative `400 invalid_argument` hint, and only a *corrected*
call (`id`/`region`) clears it. Two deliberate properties make it the right test: it is classified
**permanent** by `agent._is_retryable` (so a blind harness-retry won't touch it — that's what
separates the two guardrails), and it is **sticky** (armed per seed+tool, never re-drawn per call),
so a blind identical resend keeps failing and only a genuinely corrected call succeeds.

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
import inspect
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


# --- S6: the malformed-call fault (reject-and-hint) -----------------------
class MalformedCall(Exception):
    """A permanent, model-fixable tool rejection (a 400-style invalid-argument) — the injected
    malformed-call fault. Unlike `ToolUnavailable` (transient/retryable), a blind retry can't clear
    this; only re-calling with corrected arguments can. See DECISIONS D19."""


# Each lookup tool's *documented* parameter (the one the model naturally sends, from the schema)
# maps to the *corrected* parameter name the malformed-fault hint demands. Arming a tool rejects the
# documented name and accepts the corrected one — a clean "wrong parameter -> read the error -> fix
# it" loop. A tool whose documented param has no alias here is simply never faulted (graceful).
_PARAM_ALIAS = {
    "order_id": "id",
    "zone": "region",
}


def _documented_param(fn) -> str | None:
    """The single parameter name a lookup tool documents (what the model naturally sends)."""
    params = list(inspect.signature(fn).parameters)
    return params[0] if params else None


def with_malformed_faults(scenario: Scenario = ORDER_SCENARIO, *, rate: float, seed: int) -> Scenario:
    """Return a copy of `scenario` whose lookup tools may reject the *documented* parameter.

    For each tool, a seeded draw keyed on (seed, tool-name) decides whether that tool is **armed**
    for this scenario, with probability `rate`. An armed tool:
      - rejects a call using the documented parameter (`order_id`/`zone`) with an informative
        `MalformedCall("400 invalid_argument: … use 'id'/'region' instead")`, and
      - accepts a *corrected* call (using the aliased parameter) — returning the real record.
    An unarmed tool behaves exactly like the clean tool.

    Two load-bearing properties (DECISIONS D19): the rejection is **permanent** (classified
    non-retryable by `agent._is_retryable`, so error-recovery won't touch it) and **sticky** (armed
    per seed+tool, not re-drawn per call — a blind identical resend keeps failing; only a corrected
    call clears it). `rate=0.0` reproduces the original behavior exactly.
    """
    if not 0.0 <= rate <= 1.0:
        raise ValueError(f"rate must be in [0.0, 1.0], got {rate!r}")

    def wrap(tool_name, fn):
        documented = _documented_param(fn)
        corrected = _PARAM_ALIAS.get(documented)
        # Armed once per (seed, tool) -> sticky across every call to this tool in this scenario.
        armed = corrected is not None and random.Random(f"{seed}:{tool_name}").random() < rate

        @functools.wraps(fn)
        def faulty(**kwargs):
            if corrected is not None and corrected in kwargs:
                # The model corrected its call — accept it, mapping back to the real parameter.
                return fn(**{documented: kwargs[corrected]})
            if armed:
                raise MalformedCall(
                    f"400 invalid_argument: {tool_name} received unrecognized parameter "
                    f"{documented!r}; call {tool_name} with {corrected!r} instead "
                    f"(e.g. {tool_name}({corrected}=...))."
                )
            return fn(**kwargs)
        return faulty

    faulty_registry = {name: wrap(name, fn) for name, fn in scenario.registry.items()}
    return replace(scenario, name=f"{scenario.name}__malformed{rate}", registry=faulty_registry)
