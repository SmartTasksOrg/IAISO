"""Events vector runner.

For each vector, construct an engine, feed in the steps, capture emitted
events, and compare against the expected stream per spec/events/README.md §5.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from iaiso.conformance import ScriptedClock, VectorResult, load_vectors


def run_events_vectors(spec_root: Path) -> list[VectorResult]:
    from iaiso.audit import MemorySink
    from iaiso.core.engine import PressureConfig, PressureEngine, StepInput

    data = load_vectors(spec_root, "events")
    tolerance = float(data.get("tolerance", 1e-9))
    results: list[VectorResult] = []

    for vec in data["vectors"]:
        name = vec["name"]
        try:
            results.append(_run_events_vector(
                name, vec, tolerance, PressureConfig, PressureEngine, StepInput, MemorySink,
            ))
        except Exception as exc:  # noqa: BLE001
            results.append(VectorResult(
                section="events", name=name, passed=False,
                message=f"runner exception: {type(exc).__name__}: {exc}",
            ))

    return results


def _run_events_vector(
    name, vec, tolerance, PressureConfig, PressureEngine, StepInput, MemorySink,
):
    config = PressureConfig(**vec.get("config", {}))
    clock = ScriptedClock(vec["clock"])
    audit = MemorySink()
    execution_id = vec.get("execution_id", f"exec-events-{name}")

    engine = PressureEngine(
        config,
        execution_id=execution_id,
        audit_sink=audit,
        clock=clock,
    )

    reset_after = vec.get("reset_after_step")
    for i, step in enumerate(vec.get("steps", [])):
        engine.step(StepInput(
            tokens=step.get("tokens", 0),
            tool_calls=step.get("tool_calls", 0),
            depth=step.get("depth", 0),
            tag=step.get("tag"),
        ))
        if reset_after == i + 1:
            new_clock = vec.get("clock_after_reset")
            if new_clock is not None:
                clock._values.insert(clock._index, new_clock)
            engine.reset()

    emitted = [_event_to_dict(e) for e in audit.events]

    # Negative assertions: some vectors say the stream MUST NOT contain
    # a kind that, given the config, shouldn't appear. We check by
    # seeing if the expected_events list is a prefix or full match.
    expected = vec["expected_events"]

    # Check length: emitted must contain AT LEAST len(expected) events
    if len(emitted) < len(expected):
        return VectorResult(
            section="events", name=name, passed=False,
            message=f"expected at least {len(expected)} events, got {len(emitted)}",
            details={"emitted": emitted, "expected": expected},
        )

    # For a strict spec, a conformant impl should emit EXACTLY the
    # expected events — not extras, not fewer — UNLESS the vector says
    # otherwise. We use strict equality unless `expected_at_least` is set.
    strict = vec.get("strict_length", True)
    if strict and len(emitted) != len(expected):
        return VectorResult(
            section="events", name=name, passed=False,
            message=f"expected exactly {len(expected)} events, got {len(emitted)}",
            details={"emitted": emitted, "expected": expected},
        )

    for i, (e_actual, e_expected) in enumerate(zip(emitted, expected)):
        mismatch = _compare_event(e_actual, e_expected, tolerance)
        if mismatch:
            return VectorResult(
                section="events", name=name, passed=False,
                message=f"event[{i}] ({e_expected.get('kind', '?')}): {mismatch}",
                details={"actual": e_actual, "expected": e_expected},
            )

    return VectorResult(section="events", name=name, passed=True)


def _event_to_dict(event) -> dict[str, Any]:
    return {
        "schema_version": event.schema_version,
        "execution_id": event.execution_id,
        "kind": event.kind,
        "timestamp": event.timestamp,
        "data": dict(event.data),
    }


def _compare_event(actual: dict, expected: dict, tolerance: float) -> str | None:
    """Return None if matches, else a mismatch message. See spec §5: compare
    schema_version, execution_id, kind, and every payload field listed in
    `expected`. Ignore `timestamp`. Ignore unspecified payload fields."""

    for key in ("schema_version", "execution_id", "kind"):
        if key not in expected:
            continue
        if actual.get(key) != expected[key]:
            return f"{key}: expected {expected[key]!r}, got {actual.get(key)!r}"

    expected_data = expected.get("data", {})
    actual_data = actual.get("data", {})
    for k, v in expected_data.items():
        if k not in actual_data:
            return f"data missing required key {k!r}"
        av = actual_data[k]
        if isinstance(v, (int, float)) and isinstance(av, (int, float)):
            if abs(float(av) - float(v)) > tolerance:
                return f"data.{k}: expected {v!r}, got {av!r}"
        elif av != v:
            return f"data.{k}: expected {v!r}, got {av!r}"

    return None
