"""IAIso conformance test runner.

Loads the normative test vectors in `spec/*/vectors.json` and runs them
against this implementation. Every conformant implementation (Python,
Node, Go, Rust, Java, ...) should run an equivalent runner as part of
its test suite.

The Python runner is the reference: if a vector passes here, the vector
is considered executable. If a vector fails here, either the
implementation has regressed or the vector is wrong. Either case is a
spec-level concern.

Usage from pytest:
    pytest tests/test_conformance.py -v

Usage as a script:
    python -m iaiso.conformance spec/
    python -m iaiso.conformance spec/ --section pressure
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable


__all__ = [
    "VectorResult",
    "ScriptedClock",
    "load_vectors",
    "run_pressure_vectors",
    "run_consent_vectors",
    "run_events_vectors",
    "run_policy_vectors",
]


# --- Primitives ---

class ScriptedClock:
    """A clock that returns a predetermined sequence of values.

    Engine tests require deterministic clocks. `ScriptedClock([0.0, 0.1,
    0.2])` returns `0.0` on the first call, `0.1` on the second, and so
    on. Reaching the end raises `IndexError` so over-consumption is
    visible rather than silent.
    """

    def __init__(self, values: Iterable[float]) -> None:
        self._values = list(values)
        self._index = 0

    def __call__(self) -> float:
        if self._index >= len(self._values):
            raise IndexError(
                f"ScriptedClock exhausted after {self._index} calls; "
                f"impl consumed more clock values than the vector specified"
            )
        v = self._values[self._index]
        self._index += 1
        return v

    @property
    def consumed(self) -> int:
        return self._index


@dataclass
class VectorResult:
    """Outcome of running a single conformance vector."""

    section: str
    """Subsystem: 'pressure', 'consent', 'events', 'policy'."""

    name: str
    """Vector name from the spec file."""

    passed: bool
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        icon = "✓" if self.passed else "✗"
        return f"{icon} {self.section}/{self.name}{': ' + self.message if self.message else ''}"


def load_vectors(spec_root: Path, section: str) -> dict[str, Any]:
    """Load `spec/<section>/vectors.json`."""
    path = Path(spec_root) / section / "vectors.json"
    if not path.exists():
        raise FileNotFoundError(f"No vectors file at {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


# --- Pressure vectors ---

def run_pressure_vectors(spec_root: Path) -> list[VectorResult]:
    """Run every pressure vector against `iaiso.core.engine.PressureEngine`."""
    from iaiso.core.engine import PressureConfig, PressureEngine, StepInput

    data = load_vectors(spec_root, "pressure")
    tolerance = float(data.get("tolerance", 1e-9))
    results: list[VectorResult] = []

    for vec in data["vectors"]:
        name = vec["name"]
        # Invalid-config vectors check validation behavior, not runtime
        if "expect_config_error" in vec:
            results.append(_run_config_error_vector(
                name, vec, PressureConfig,
            ))
            continue

        try:
            results.append(_run_pressure_trajectory(
                name, vec, tolerance, PressureConfig, PressureEngine, StepInput,
            ))
        except Exception as exc:  # noqa: BLE001
            results.append(VectorResult(
                section="pressure",
                name=name,
                passed=False,
                message=f"runner exception: {type(exc).__name__}: {exc}",
            ))

    return results


def _run_config_error_vector(
    name: str, vec: dict, PressureConfig: type,
) -> VectorResult:
    expected_substr = vec["expect_config_error"]
    try:
        PressureConfig(**vec["config"])
    except (ValueError, TypeError) as exc:
        if expected_substr in str(exc):
            return VectorResult(section="pressure", name=name, passed=True)
        return VectorResult(
            section="pressure", name=name, passed=False,
            message=f"got error {exc!s} but expected substring {expected_substr!r}",
        )
    return VectorResult(
        section="pressure", name=name, passed=False,
        message=f"expected config validation error containing {expected_substr!r} but config was accepted",
    )


def _run_pressure_trajectory(
    name: str,
    vec: dict,
    tolerance: float,
    PressureConfig: type,
    PressureEngine: type,
    StepInput: type,
) -> VectorResult:
    from iaiso.audit import MemorySink

    config = PressureConfig(**vec.get("config", {}))
    clock = ScriptedClock(vec["clock"])
    audit = MemorySink()

    engine = PressureEngine(
        config,
        execution_id=f"conformance-{name}",
        audit_sink=audit,
        clock=clock,
    )

    # Check initial state if the vector specifies it
    if "expected_initial" in vec:
        init = vec["expected_initial"]
        snap = engine.snapshot()
        for field_name, expected in init.items():
            actual = getattr(snap, field_name)
            if not _approx_equal(actual, expected, tolerance):
                return VectorResult(
                    section="pressure", name=name, passed=False,
                    message=f"initial {field_name}: expected {expected!r}, got {actual!r}",
                )

    # Run steps
    steps = vec.get("steps", [])
    expected_steps = vec.get("expected_steps", [])
    reset_after_step = vec.get("reset_after_step")

    for i, step_input in enumerate(steps):
        outcome = engine.step(StepInput(
            tokens=step_input.get("tokens", 0),
            tool_calls=step_input.get("tool_calls", 0),
            depth=step_input.get("depth", 0),
            tag=step_input.get("tag"),
        ))
        expected = expected_steps[i]

        # Check pressure
        if "pressure" in expected:
            if not _approx_equal(engine.pressure, expected["pressure"], tolerance):
                return VectorResult(
                    section="pressure", name=name, passed=False,
                    message=f"step {i+1}: pressure expected {expected['pressure']!r}, got {engine.pressure!r}",
                )

        # Check outcome
        if "outcome" in expected:
            if outcome.value != expected["outcome"]:
                return VectorResult(
                    section="pressure", name=name, passed=False,
                    message=f"step {i+1}: outcome expected {expected['outcome']!r}, got {outcome.value!r}",
                )

        # Check lifecycle
        if "lifecycle" in expected:
            if engine.lifecycle.value != expected["lifecycle"]:
                return VectorResult(
                    section="pressure", name=name, passed=False,
                    message=f"step {i+1}: lifecycle expected {expected['lifecycle']!r}, got {engine.lifecycle.value!r}",
                )

        # Check step counter
        if "step" in expected:
            if engine.snapshot().step != expected["step"]:
                return VectorResult(
                    section="pressure", name=name, passed=False,
                    message=f"step {i+1}: step counter expected {expected['step']!r}, got {engine.snapshot().step!r}",
                )

        # Check delta/decay via emitted event (only populated on non-rejected steps)
        if "delta" in expected or "decay" in expected:
            step_events = [e for e in audit.events if e.kind == "engine.step"]
            if step_events:
                latest = step_events[-1]
                if "delta" in expected and not _approx_equal(
                    latest.data["delta"], expected["delta"], tolerance,
                ):
                    return VectorResult(
                        section="pressure", name=name, passed=False,
                        message=f"step {i+1}: delta expected {expected['delta']!r}, got {latest.data['delta']!r}",
                    )
                if "decay" in expected and not _approx_equal(
                    latest.data["decay"], expected["decay"], tolerance,
                ):
                    return VectorResult(
                        section="pressure", name=name, passed=False,
                        message=f"step {i+1}: decay expected {expected['decay']!r}, got {latest.data['decay']!r}",
                    )

        if reset_after_step == i + 1:
            # Advance the scripted clock: the vector's `clock_after_reset`
            # is the NEXT clock value. We need it to be the clock's next
            # value, but since ScriptedClock pulls sequentially, the vector
            # author should have placed it at the right offset in the clock
            # array. We re-seed the clock by splicing in the new value.
            new_val = vec.get("clock_after_reset")
            if new_val is not None:
                clock._values.insert(clock._index, new_val)
            engine.reset()

    # Check post-reset state
    if "expected_after_reset" in vec:
        snap = engine.snapshot()
        for field_name, expected in vec["expected_after_reset"].items():
            actual = getattr(snap, field_name)
            if not _approx_equal(actual, expected, tolerance):
                return VectorResult(
                    section="pressure", name=name, passed=False,
                    message=f"post-reset {field_name}: expected {expected!r}, got {actual!r}",
                )

    return VectorResult(section="pressure", name=name, passed=True)


def _approx_equal(actual: Any, expected: Any, tolerance: float) -> bool:
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return abs(float(actual) - float(expected)) <= tolerance
    return actual == expected


# --- Consent vectors (implemented later in this package) ---

def run_consent_vectors(spec_root: Path) -> list[VectorResult]:
    from iaiso.conformance._consent import run_consent_vectors as _impl
    return _impl(spec_root)


def run_events_vectors(spec_root: Path) -> list[VectorResult]:
    from iaiso.conformance._events import run_events_vectors as _impl
    return _impl(spec_root)


def run_policy_vectors(spec_root: Path) -> list[VectorResult]:
    from iaiso.conformance._policy import run_policy_vectors as _impl
    return _impl(spec_root)


# --- Top-level runner ---

def run_all(spec_root: Path) -> dict[str, list[VectorResult]]:
    """Run every available conformance section. Returns per-section results."""
    results: dict[str, list[VectorResult]] = {}
    runners: list[tuple[str, Callable[[Path], list[VectorResult]]]] = [
        ("pressure", run_pressure_vectors),
        ("consent", run_consent_vectors),
        ("events", run_events_vectors),
        ("policy", run_policy_vectors),
    ]
    for section, fn in runners:
        try:
            results[section] = fn(spec_root)
        except FileNotFoundError:
            # Section not yet populated — skip quietly.
            results[section] = []
        except Exception as exc:  # noqa: BLE001
            results[section] = [VectorResult(
                section=section, name="<runner>",
                passed=False,
                message=f"{type(exc).__name__}: {exc}",
            )]
    return results
