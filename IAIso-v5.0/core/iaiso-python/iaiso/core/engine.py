"""Core pressure-accumulation model.

The pressure model tracks cost accumulation for an agent execution. Pressure rises
with each operation (tokens generated, tools called, planning steps taken) and
decays over time (dissipation). When pressure crosses the release threshold, the
engine signals that a reset is required.

The pressure engine is IAIso's runtime rate-limiting primitive. It composes
with higher-level controls (Layer 0 process/hardware anchors, Layer 4
human-in-the-loop escalation, Layer 6 existential safeguards) as specified
in the framework. Coefficients are configuration — calibrate them for the
target workload using `iaiso.evaluation`. See `../../../spec/pressure/README.md`
for the normative specification.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from iaiso.audit import AuditEvent, AuditSink, NullSink


class Lifecycle(str, Enum):
    """Lifecycle states for a pressure-bounded execution."""

    INIT = "init"
    RUNNING = "running"
    ESCALATED = "escalated"
    RELEASED = "released"
    LOCKED = "locked"


class StepOutcome(str, Enum):
    """Outcome returned from `PressureEngine.step()`."""

    OK = "ok"
    ESCALATED = "escalated"
    RELEASED = "released"
    LOCKED = "locked"


@dataclass(frozen=True)
class PressureConfig:
    """Configuration for the pressure model.

    All coefficients have explicit units and defaults that should be treated as
    placeholders. Real deployments must calibrate these against measured workload
    behavior. See `iaiso.evaluation.calibrate`.

    Attributes:
        escalation_threshold: Pressure level at which the engine signals that human
            review or intervention is needed. Range [0.0, 1.0]. Default 0.85.
        release_threshold: Pressure level at which the engine forces a state reset.
            Must be > escalation_threshold. Range [0.0, 1.0]. Default 0.95.
        dissipation_per_step: Amount of pressure that decays per step, independent
            of wall-clock time. Default 0.02.
        dissipation_per_second: Additional decay rate based on elapsed wall time
            between steps. Set to 0.0 to use step-count dissipation only. Default 0.0.
        token_coefficient: Pressure added per 1000 tokens generated. Default 0.015.
        tool_coefficient: Pressure added per tool call. Default 0.08.
        depth_coefficient: Pressure added per level of planning/recursion depth.
            Default 0.05.
        post_release_lock: If True, the engine refuses further steps after a release
            until explicitly reset via `reset()`. If False, pressure continues
            accumulating from zero. Default True.
    """

    escalation_threshold: float = 0.85
    release_threshold: float = 0.95
    dissipation_per_step: float = 0.02
    dissipation_per_second: float = 0.0
    token_coefficient: float = 0.015
    tool_coefficient: float = 0.08
    depth_coefficient: float = 0.05
    post_release_lock: bool = True

    def __post_init__(self) -> None:
        if not 0.0 <= self.escalation_threshold <= 1.0:
            raise ValueError("escalation_threshold must be in [0, 1]")
        if not 0.0 <= self.release_threshold <= 1.0:
            raise ValueError("release_threshold must be in [0, 1]")
        if self.release_threshold <= self.escalation_threshold:
            raise ValueError("release_threshold must exceed escalation_threshold")
        for name in ("dissipation_per_step", "dissipation_per_second",
                     "token_coefficient", "tool_coefficient", "depth_coefficient"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be non-negative")


@dataclass
class StepInput:
    """Single unit of work to account for pressure."""

    tokens: int = 0
    tool_calls: int = 0
    depth: int = 0
    tag: str | None = None
    """Optional string tag propagated into audit events, e.g. the operation name."""


@dataclass
class PressureSnapshot:
    """Immutable view of the engine state at a point in time."""

    pressure: float
    step: int
    lifecycle: Lifecycle
    last_delta: float
    last_step_at: float


class PressureEngine:
    """Tracks pressure accumulation for a single bounded execution.

    The engine is single-threaded and stateful. For concurrent executions, create
    one engine per execution. For shared cross-execution limits, see
    `iaiso.core.shared.SharedPressureCoordinator` (not yet implemented).

    Example:
        >>> cfg = PressureConfig()
        >>> engine = PressureEngine(cfg, execution_id="exec-123")
        >>> outcome = engine.step(StepInput(tokens=500, tool_calls=1))
        >>> if outcome is StepOutcome.ESCALATED:
        ...     # pause and request human review
        ...     pass
    """

    def __init__(
        self,
        config: PressureConfig,
        execution_id: str,
        audit_sink: AuditSink | None = None,
        clock: Any = time.monotonic,
    ) -> None:
        self._cfg = config
        self._execution_id = execution_id
        self._audit = audit_sink or NullSink()
        self._clock = clock

        self._pressure: float = 0.0
        self._step: int = 0
        self._lifecycle: Lifecycle = Lifecycle.INIT
        self._last_delta: float = 0.0
        self._last_step_at: float = self._clock()

        self._emit("engine.init", pressure=self._pressure)

    @property
    def config(self) -> PressureConfig:
        return self._cfg

    @property
    def execution_id(self) -> str:
        return self._execution_id

    @property
    def pressure(self) -> float:
        return self._pressure

    @property
    def lifecycle(self) -> Lifecycle:
        return self._lifecycle

    def snapshot(self) -> PressureSnapshot:
        return PressureSnapshot(
            pressure=self._pressure,
            step=self._step,
            lifecycle=self._lifecycle,
            last_delta=self._last_delta,
            last_step_at=self._last_step_at,
        )

    def step(self, work: StepInput) -> StepOutcome:
        """Account for a unit of work and advance the engine.

        Returns:
            OK: Pressure is below the escalation threshold. Continue normally.
            ESCALATED: Pressure crossed the escalation threshold. The caller
                should pause and request human review or take its configured
                escalation action. Further steps are still accepted.
            RELEASED: Pressure crossed the release threshold. State has been
                wiped. If `post_release_lock` is True, the engine is now LOCKED
                and will reject further steps until `reset()` is called.
            LOCKED: The engine is in the post-release locked state and refused
                this step. The caller must call `reset()` before continuing.
        """
        if self._lifecycle is Lifecycle.LOCKED:
            self._emit("engine.step.rejected",
                       reason="locked",
                       requested_tokens=work.tokens,
                       requested_tools=work.tool_calls)
            return StepOutcome.LOCKED

        now = self._clock()
        elapsed = max(0.0, now - self._last_step_at)

        delta = (
            (work.tokens / 1000.0) * self._cfg.token_coefficient
            + work.tool_calls * self._cfg.tool_coefficient
            + work.depth * self._cfg.depth_coefficient
        )
        decay = (
            self._cfg.dissipation_per_step
            + elapsed * self._cfg.dissipation_per_second
        )

        self._pressure = max(0.0, min(1.0, self._pressure + delta - decay))
        self._step += 1
        self._last_delta = delta - decay
        self._last_step_at = now
        self._lifecycle = Lifecycle.RUNNING

        self._emit(
            "engine.step",
            step=self._step,
            pressure=self._pressure,
            delta=delta,
            decay=decay,
            tokens=work.tokens,
            tool_calls=work.tool_calls,
            depth=work.depth,
            tag=work.tag,
        )

        if self._pressure >= self._cfg.release_threshold:
            return self._release()
        if self._pressure >= self._cfg.escalation_threshold:
            self._lifecycle = Lifecycle.ESCALATED
            self._emit("engine.escalation",
                       pressure=self._pressure,
                       threshold=self._cfg.escalation_threshold)
            return StepOutcome.ESCALATED
        return StepOutcome.OK

    def _release(self) -> StepOutcome:
        prior_pressure = self._pressure
        self._lifecycle = Lifecycle.RELEASED
        self._emit("engine.release",
                   pressure=prior_pressure,
                   threshold=self._cfg.release_threshold)

        self._pressure = 0.0
        if self._cfg.post_release_lock:
            self._lifecycle = Lifecycle.LOCKED
            self._emit("engine.locked", reason="post_release_lock")
        else:
            self._lifecycle = Lifecycle.RUNNING

        return StepOutcome.RELEASED

    def reset(self) -> PressureSnapshot:
        """Clear pressure and unlock the engine. Emits an audit event."""
        self._pressure = 0.0
        self._step = 0
        self._last_delta = 0.0
        self._last_step_at = self._clock()
        self._lifecycle = Lifecycle.INIT
        self._emit("engine.reset", pressure=self._pressure)
        return self.snapshot()

    def _emit(self, kind: str, **data: Any) -> None:
        self._audit.emit(AuditEvent(
            execution_id=self._execution_id,
            kind=kind,
            timestamp=time.time(),
            data=data,
        ))
