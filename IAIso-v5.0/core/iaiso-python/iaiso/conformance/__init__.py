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
import logging
from contextlib import contextmanager
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


def load_vectors(spec_root: Path, section: str,
                 filename: str = "vectors.json") -> dict[str, Any]:
    """Load `spec/<section>/<filename>` (default `vectors.json`)."""
    path = Path(spec_root) / section / filename
    if not path.exists():
        raise FileNotFoundError(f"No vectors file at {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


# --- Pressure vectors ---

def run_pressure_vectors(spec_root: Path,
                         filename: str = "vectors.json") -> list[VectorResult]:
    """Run every pressure vector against `iaiso.core.engine.PressureEngine`.
    A 1.x file replays under `PressureConfig.v1`; a 2.x file under 2.0 defaults."""
    from iaiso.core.engine import PressureConfig, PressureEngine, StepInput

    data = load_vectors(spec_root, "pressure", filename)
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
                name, vec, tolerance, _profile_for(data, PressureConfig),
                PressureEngine, StepInput,
            ))
        except Exception as exc:  # noqa: BLE001
            results.append(VectorResult(
                section="pressure",
                name=name,
                passed=False,
                message=f"runner exception: {type(exc).__name__}: {exc}",
            ))

    return results


def _profile_for(data: dict, PressureConfig: type) -> Any:
    """1.x vector files pin 1.x semantics, so they replay under
    `PressureConfig.v1`; 2.x files use the 2.0 defaults."""
    version = str(data.get("version", "1"))
    if version.split(".")[0] == "1" and hasattr(PressureConfig, "v1"):
        return PressureConfig.v1
    return PressureConfig


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
            model=step_input.get("model"),
        ))
        expected = expected_steps[i]

        if "totals" in expected and engine.totals != expected["totals"]:
            return VectorResult(
                section="pressure", name=name, passed=False,
                message=f"step {i+1}: totals expected {expected['totals']!r}, got {engine.totals!r}",
            )
        if "spend_usd" in expected and not _approx_equal(
                engine.spend_usd, expected["spend_usd"], tolerance):
            return VectorResult(
                section="pressure", name=name, passed=False,
                message=f"step {i+1}: spend_usd expected {expected['spend_usd']!r}, got {engine.spend_usd!r}",
            )

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


def run_pressure_v2_vectors(spec_root: Path) -> list[VectorResult]:
    """2.0 semantics: `spec/pressure/vectors-2.json`."""
    results = run_pressure_vectors(spec_root, "vectors-2.json")
    for r in results:
        r.section = "pressure-v2"
    return results


def run_hostile_vectors(spec_root: Path) -> list[VectorResult]:
    """`spec/pressure/hostile.json`: inputs that must be refused, and extreme
    inputs that must be handled without overflow or NaN. Shared by all ports."""
    from iaiso.audit import MemorySink
    from iaiso.core.engine import PressureConfig, PressureEngine, StepInput

    data = load_vectors(spec_root, "pressure", "hostile.json")
    out: list[VectorResult] = []
    for vec in data["reject"]:
        name = vec["name"]
        try:
            work = StepInput(**{vec["field"]: vec["value"]})
            engine = PressureEngine(PressureConfig.v1(), execution_id="hostile",
                                    audit_sink=MemorySink(), clock=lambda: 0.0)
            engine.step(work)
        except (ValueError, TypeError):
            out.append(VectorResult("hostile", name, True))
            continue
        out.append(VectorResult("hostile", name, False,
                                message=f"{vec['field']}={vec['value']!r} was accepted"))
    for vec in data["accept"]:
        name = vec["name"]
        try:
            engine = PressureEngine(PressureConfig.v1(**vec.get("config", {})),
                                    execution_id="hostile", audit_sink=MemorySink(),
                                    clock=lambda: 0.0)
            outcome = engine.step(StepInput(**vec["step"]))
        except Exception as exc:  # noqa: BLE001
            out.append(VectorResult("hostile", name, False,
                                    message=f"raised {type(exc).__name__}: {exc}"))
            continue
        exp = vec["expect"]
        problems = []
        if not _approx_equal(engine.pressure, exp["pressure"], 1e-9):
            problems.append(f"pressure {engine.pressure!r} != {exp['pressure']!r}")
        if outcome.value != exp["outcome"]:
            problems.append(f"outcome {outcome.value!r} != {exp['outcome']!r}")
        if engine.lifecycle.value != exp["lifecycle"]:
            problems.append(f"lifecycle {engine.lifecycle.value!r} != {exp['lifecycle']!r}")
        out.append(VectorResult("hostile", name, not problems, message="; ".join(problems)))
    return out


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

@contextmanager
def _silence_boot_warnings():
    """Mute permissive-mode degradation warnings for the duration of a run.

    The vectors deliberately exercise degraded configurations (NullSink,
    post_release_lock=false, uncalibrated defaults). Their warnings are
    expected, and printing them would corrupt the suite's output.
    """
    logger = logging.getLogger("iaiso")
    previous = logger.disabled
    logger.disabled = True
    try:
        yield
    finally:
        logger.disabled = previous


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
            with _silence_boot_warnings():
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