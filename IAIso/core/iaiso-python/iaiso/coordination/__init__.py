"""Cross-execution pressure coordination for fleets of agents.

Single-execution `BoundedExecution` objects bound one agent in isolation. When
you have many agents sharing resources — an API quota, a database, a downstream
service with a rate limit — you want fleet-wide signals: "the system as a
whole is hot, even if no individual agent is." That's what a coordinator
provides.

Design:
    - A `SharedPressureCoordinator` tracks per-execution pressure plus an
      aggregate. Executions register with the coordinator and report pressure
      changes via `update()`.
    - Aggregation policy is pluggable: `SumAggregator`, `MeanAggregator`,
      `MaxAggregator`, `WeightedSumAggregator`. Default is `SumAggregator`.
    - The coordinator has its own escalation/release thresholds, separate
      from any individual engine's thresholds. Crossing a coordinator
      threshold emits a fleet-level audit event and invokes a callback.
    - The coordinator is thread-safe. It is designed for in-process fleets
      (e.g., a single Python worker running many async agents). For
      multi-process coordination, implement the same interface against
      Redis or a similar shared store — see `SharedStateBackend` protocol.

Threading / concurrency:
    The in-memory coordinator uses a single RLock for all state mutation.
    This is fine for dozens of concurrent agents, not for thousands. At
    high concurrency, use a `RedisCoordinator` (see `iaiso.coordination.redis`).
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from iaiso.audit import AuditEvent, AuditSink, NullSink


@dataclass(frozen=True)
class CoordinatorConfig:
    """Configuration for a cross-execution coordinator.

    Attributes:
        escalation_threshold: Aggregate pressure at which the fleet is
            flagged. Range [0, ∞). Units depend on the aggregator: for
            `SumAggregator` it's summed individual pressures, for
            `MeanAggregator` it's a [0, 1] average.
        release_threshold: Aggregate pressure at which `on_release` is
            invoked. Must exceed `escalation_threshold`.
        notify_cooldown_seconds: Minimum interval between repeated
            escalation notifications for the same threshold crossing,
            to avoid callback storms when many agents report at once.
    """

    escalation_threshold: float = 5.0
    release_threshold: float = 8.0
    notify_cooldown_seconds: float = 1.0

    def __post_init__(self) -> None:
        if self.escalation_threshold < 0:
            raise ValueError("escalation_threshold must be non-negative")
        if self.release_threshold <= self.escalation_threshold:
            raise ValueError("release_threshold must exceed escalation_threshold")
        if self.notify_cooldown_seconds < 0:
            raise ValueError("notify_cooldown_seconds must be non-negative")


class Aggregator(Protocol):
    """Combines per-execution pressures into a fleet-level scalar."""

    name: str

    def aggregate(self, pressures: dict[str, float]) -> float:
        ...


class SumAggregator:
    """Sum of individual pressures. Fleet pressure grows with fleet size."""

    name = "sum"

    def aggregate(self, pressures: dict[str, float]) -> float:
        return sum(pressures.values())


class MeanAggregator:
    """Average individual pressure. Stays bounded in [0, 1] regardless of fleet size."""

    name = "mean"

    def aggregate(self, pressures: dict[str, float]) -> float:
        if not pressures:
            return 0.0
        return sum(pressures.values()) / len(pressures)


class MaxAggregator:
    """Maximum individual pressure. Detects any single-agent runaway."""

    name = "max"

    def aggregate(self, pressures: dict[str, float]) -> float:
        if not pressures:
            return 0.0
        return max(pressures.values())


@dataclass
class WeightedSumAggregator:
    """Sum of individual pressures weighted by per-execution factors.

    Useful when some executions are more "expensive" to the shared resource
    than others (e.g., a research agent vs. a simple classification agent).
    """

    name: str = "weighted_sum"
    weights: dict[str, float] = field(default_factory=dict)
    default_weight: float = 1.0

    def aggregate(self, pressures: dict[str, float]) -> float:
        return sum(
            self.weights.get(eid, self.default_weight) * p
            for eid, p in pressures.items()
        )


@dataclass
class CoordinatorSnapshot:
    aggregate_pressure: float
    per_execution: dict[str, float]
    active_executions: int
    lifecycle: str  # "nominal" | "escalated" | "released"


class SharedPressureCoordinator:
    """In-memory coordinator for fleet-level pressure tracking.

    Usage:
        coordinator = SharedPressureCoordinator(
            config=CoordinatorConfig(escalation_threshold=3.0),
            aggregator=SumAggregator(),
            on_escalation=lambda snap: logger.warning("fleet hot: %s", snap),
        )

        # In each agent:
        exec_id = "agent-42"
        coordinator.register(exec_id)
        try:
            with BoundedExecution.start(execution_id=exec_id) as exec_:
                outcome = exec_.record_step(...)
                coordinator.update(exec_id, exec_.snapshot().pressure)
        finally:
            coordinator.unregister(exec_id)
    """

    def __init__(
        self,
        config: CoordinatorConfig | None = None,
        aggregator: Aggregator | None = None,
        audit_sink: AuditSink | None = None,
        on_escalation: Callable[[CoordinatorSnapshot], None] | None = None,
        on_release: Callable[[CoordinatorSnapshot], None] | None = None,
        coordinator_id: str | None = None,
    ) -> None:
        self._cfg = config or CoordinatorConfig()
        self._agg = aggregator or SumAggregator()
        self._audit = audit_sink or NullSink()
        self._on_escalation = on_escalation
        self._on_release = on_release
        self._id = coordinator_id or f"coord-{uuid.uuid4()}"

        self._lock = threading.RLock()
        self._pressures: dict[str, float] = {}
        self._lifecycle: str = "nominal"
        self._last_notify_at: float = 0.0

        self._emit("coordinator.init",
                   aggregator=self._agg.name,
                   escalation_threshold=self._cfg.escalation_threshold,
                   release_threshold=self._cfg.release_threshold)

    @property
    def coordinator_id(self) -> str:
        return self._id

    def register(self, execution_id: str) -> None:
        """Register an execution as part of this fleet."""
        with self._lock:
            self._pressures[execution_id] = 0.0
            self._emit("coordinator.execution_registered",
                       execution_id=execution_id,
                       fleet_size=len(self._pressures))

    def unregister(self, execution_id: str) -> None:
        """Remove an execution from the fleet (e.g., on completion)."""
        with self._lock:
            self._pressures.pop(execution_id, None)
            self._emit("coordinator.execution_unregistered",
                       execution_id=execution_id,
                       fleet_size=len(self._pressures))
            self._check_release()

    def update(self, execution_id: str, pressure: float) -> CoordinatorSnapshot:
        """Report the current pressure of an execution. Returns a fleet snapshot."""
        if not 0.0 <= pressure <= 1.0:
            raise ValueError("pressure must be in [0, 1]")
        with self._lock:
            if execution_id not in self._pressures:
                # Auto-register for ergonomics. Log it so misuse is visible.
                self._pressures[execution_id] = 0.0
                self._emit("coordinator.auto_registered",
                           execution_id=execution_id)
            self._pressures[execution_id] = pressure
            # Compute aggregate and check transitions BEFORE taking the
            # returned snapshot, so callers see the post-transition state.
            pre_snap = self._snapshot_locked()
            self._check_transitions_locked(pre_snap)
            return self._snapshot_locked()

    def snapshot(self) -> CoordinatorSnapshot:
        with self._lock:
            return self._snapshot_locked()

    def _snapshot_locked(self) -> CoordinatorSnapshot:
        agg = self._agg.aggregate(self._pressures)
        return CoordinatorSnapshot(
            aggregate_pressure=agg,
            per_execution=dict(self._pressures),
            active_executions=len(self._pressures),
            lifecycle=self._lifecycle,
        )

    def _check_transitions_locked(self, snap: CoordinatorSnapshot) -> None:
        now = time.monotonic()
        agg = snap.aggregate_pressure

        if agg >= self._cfg.release_threshold and self._lifecycle != "released":
            self._lifecycle = "released"
            self._emit("coordinator.release",
                       aggregate_pressure=agg,
                       threshold=self._cfg.release_threshold,
                       fleet_size=len(self._pressures))
            if self._on_release is not None:
                try:
                    self._on_release(snap)
                except Exception as exc:  # noqa: BLE001
                    self._emit("coordinator.callback_error",
                               callback="on_release",
                               error=str(exc))
        elif (agg >= self._cfg.escalation_threshold
              and self._lifecycle == "nominal"):
            self._lifecycle = "escalated"
            self._last_notify_at = now
            self._emit("coordinator.escalation",
                       aggregate_pressure=agg,
                       threshold=self._cfg.escalation_threshold,
                       fleet_size=len(self._pressures))
            if self._on_escalation is not None:
                try:
                    self._on_escalation(snap)
                except Exception as exc:  # noqa: BLE001
                    self._emit("coordinator.callback_error",
                               callback="on_escalation",
                               error=str(exc))
        elif (self._lifecycle == "escalated"
              and agg >= self._cfg.escalation_threshold
              and now - self._last_notify_at
              >= self._cfg.notify_cooldown_seconds
              and self._on_escalation is not None):
            self._last_notify_at = now
            try:
                self._on_escalation(snap)
            except Exception as exc:  # noqa: BLE001
                self._emit("coordinator.callback_error",
                           callback="on_escalation",
                           error=str(exc))

    def _check_release(self) -> None:
        # Re-evaluate after unregister in case removing an execution drops
        # aggregate below thresholds.
        snap = self._snapshot_locked()
        if (self._lifecycle != "nominal"
                and snap.aggregate_pressure < self._cfg.escalation_threshold):
            self._lifecycle = "nominal"
            self._emit("coordinator.returned_to_nominal",
                       aggregate_pressure=snap.aggregate_pressure,
                       fleet_size=snap.active_executions)

    def reset(self) -> None:
        """Clear all execution pressure. Useful after fleet-level escalation
        has been handled externally and the operator wants to resume."""
        with self._lock:
            for eid in self._pressures:
                self._pressures[eid] = 0.0
            self._lifecycle = "nominal"
            self._emit("coordinator.reset",
                       fleet_size=len(self._pressures))

    def _emit(self, kind: str, **data: Any) -> None:
        self._audit.emit(AuditEvent(
            execution_id=self._id,
            kind=kind,
            timestamp=time.time(),
            data=data,
        ))
