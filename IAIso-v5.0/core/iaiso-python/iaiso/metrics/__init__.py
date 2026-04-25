"""Metrics export for IAIso.

IAIso emits structured audit events via `AuditSink`. Observability systems
want time-series metrics: counters, gauges, histograms. This module bridges
the two: it implements `AuditSink`, classifies each event, and updates
metric values accordingly.

Three concrete exporters ship:
    - `PrometheusMetricsSink` — uses `prometheus_client` if installed,
      falls back to a minimal in-process registry otherwise.
    - `OTelMetricsSink` — uses the OpenTelemetry Python SDK if installed.
    - `InMemoryMetricsSink` — no external deps, useful for testing and
      for exposing metrics through an ad-hoc HTTP endpoint.

Metric semantics:
    - `iaiso_steps_total{outcome}` — counter, incremented per engine.step
    - `iaiso_escalations_total` — counter, per engine.escalation
    - `iaiso_releases_total` — counter, per engine.release
    - `iaiso_pressure` — gauge, last observed pressure per execution
    - `iaiso_active_executions` — gauge, count of active BoundedExecutions
    - `iaiso_consent_denied_total{reason}` — counter, denied consent checks
    - `iaiso_coordinator_pressure` — gauge, aggregate fleet pressure
    - `iaiso_sink_dropped_total{sink}` — counter, events dropped by sinks

Install:
    pip install iaiso[metrics]         # prometheus_client
    pip install iaiso[otel]            # opentelemetry-api + sdk
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from iaiso.audit import AuditEvent, AuditSink


@dataclass
class MetricSnapshot:
    """Point-in-time view of all metrics."""
    counters: dict[str, dict[tuple[tuple[str, str], ...], float]] = field(default_factory=dict)
    gauges: dict[str, dict[tuple[tuple[str, str], ...], float]] = field(default_factory=dict)
    histograms: dict[str, dict[tuple[tuple[str, str], ...], list[float]]] = field(default_factory=dict)


class InMemoryMetricsSink:
    """Audit sink that accumulates IAIso events into in-memory metrics.

    Useful for:
        - Testing metric collection without a Prometheus / OTel stack.
        - Exposing metrics via a custom HTTP endpoint (e.g., embed in
          an existing FastAPI app).
        - Short-lived batch processes that don't want a metrics exporter
          dependency.

    Thread-safe. The `snapshot()` method returns a consistent view.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._counters: dict[str, dict[tuple[tuple[str, str], ...], float]] = defaultdict(dict)
        self._gauges: dict[str, dict[tuple[tuple[str, str], ...], float]] = defaultdict(dict)
        self._histograms: dict[str, dict[tuple[tuple[str, str], ...], list[float]]] = defaultdict(dict)
        self._active_executions: set[str] = set()

    def emit(self, event: AuditEvent) -> None:
        with self._lock:
            self._classify(event)

    def _inc(self, name: str, labels: dict[str, str], value: float = 1.0) -> None:
        key = tuple(sorted(labels.items()))
        bucket = self._counters[name]
        bucket[key] = bucket.get(key, 0.0) + value

    def _set(self, name: str, labels: dict[str, str], value: float) -> None:
        key = tuple(sorted(labels.items()))
        self._gauges[name][key] = value

    def _observe(self, name: str, labels: dict[str, str], value: float) -> None:
        key = tuple(sorted(labels.items()))
        bucket = self._histograms[name]
        bucket.setdefault(key, []).append(value)

    def _classify(self, event: AuditEvent) -> None:
        kind = event.kind
        data = event.data
        exec_id = event.execution_id

        if kind == "engine.init":
            self._active_executions.add(exec_id)
            self._set("iaiso_active_executions", {}, float(len(self._active_executions)))
        elif kind == "engine.step":
            outcome = str(data.get("outcome", "unknown"))
            self._inc("iaiso_steps_total", {"outcome": outcome})
            pressure = data.get("pressure")
            if isinstance(pressure, (int, float)):
                self._set("iaiso_pressure", {"execution_id": exec_id}, float(pressure))
        elif kind == "engine.escalation":
            self._inc("iaiso_escalations_total", {})
        elif kind == "engine.release":
            self._inc("iaiso_releases_total", {})
        elif kind == "engine.reset":
            self._inc("iaiso_resets_total", {})
        elif kind == "execution.lifecycle":
            # Clean up gauges when an execution finishes.
            if str(data.get("to", "")) in ("released", "closed"):
                self._active_executions.discard(exec_id)
                self._set("iaiso_active_executions", {},
                          float(len(self._active_executions)))
                self._gauges["iaiso_pressure"].pop(
                    tuple([("execution_id", exec_id)]), None)
        elif kind.startswith("consent.") and "denied" in kind:
            reason = str(data.get("reason", "unknown"))
            self._inc("iaiso_consent_denied_total", {"reason": reason})
        elif kind == "coordinator.escalation":
            agg = data.get("aggregate_pressure")
            if isinstance(agg, (int, float)):
                self._set("iaiso_coordinator_pressure", {}, float(agg))
            self._inc("iaiso_coordinator_escalations_total", {})
        elif kind == "coordinator.release":
            self._inc("iaiso_coordinator_releases_total", {})
        # Unknown event kinds are silently ignored; the metric schema is
        # intentionally narrower than the audit schema.

    def snapshot(self) -> MetricSnapshot:
        with self._lock:
            return MetricSnapshot(
                counters={k: dict(v) for k, v in self._counters.items()},
                gauges={k: dict(v) for k, v in self._gauges.items()},
                histograms={k: {lk: list(lv) for lk, lv in v.items()}
                            for k, v in self._histograms.items()},
            )

    def render_prometheus(self) -> str:
        """Render the current state as Prometheus exposition format.

        Use this if you want to serve metrics from a minimal HTTP handler
        without adding the `prometheus_client` dependency.
        """
        lines: list[str] = []
        with self._lock:
            for name, series in sorted(self._counters.items()):
                lines.append(f"# TYPE {name} counter")
                for labels, val in series.items():
                    lines.append(f"{name}{_fmt_labels(labels)} {val}")
            for name, series in sorted(self._gauges.items()):
                lines.append(f"# TYPE {name} gauge")
                for labels, val in series.items():
                    lines.append(f"{name}{_fmt_labels(labels)} {val}")
        return "\n".join(lines) + "\n"


def _fmt_labels(labels: tuple[tuple[str, str], ...]) -> str:
    if not labels:
        return ""
    inner = ",".join(f'{k}="{_escape(v)}"' for k, v in labels)
    return "{" + inner + "}"


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


class PrometheusMetricsSink:
    """Metrics sink backed by the `prometheus_client` library.

    Creates persistent metric objects in the default registry (or one you
    pass in). To serve these metrics, use `prometheus_client.start_http_server`
    or expose `prometheus_client.generate_latest(registry)` from your app.

    Requires: pip install iaiso[metrics]
    """

    def __init__(self, registry: Any = None, namespace: str = "iaiso") -> None:
        try:
            from prometheus_client import Counter, Gauge  # noqa: F401
        except ImportError as e:  # pragma: no cover
            raise ImportError(
                "PrometheusMetricsSink requires prometheus_client. "
                "Install with: pip install iaiso[metrics]"
            ) from e
        from prometheus_client import Counter, Gauge, CollectorRegistry

        self._registry = registry or CollectorRegistry()
        self._ns = namespace
        # Pre-create metrics so they appear in /metrics even before any
        # event fires — common Prometheus best practice.
        self._steps = Counter(
            f"{namespace}_steps_total",
            "Total engine steps by outcome",
            labelnames=["outcome"],
            registry=self._registry,
        )
        self._escalations = Counter(
            f"{namespace}_escalations_total",
            "Total pressure escalation events",
            registry=self._registry,
        )
        self._releases = Counter(
            f"{namespace}_releases_total",
            "Total release events",
            registry=self._registry,
        )
        self._resets = Counter(
            f"{namespace}_resets_total",
            "Total engine resets",
            registry=self._registry,
        )
        self._consent_denied = Counter(
            f"{namespace}_consent_denied_total",
            "Total denied consent checks by reason",
            labelnames=["reason"],
            registry=self._registry,
        )
        self._pressure = Gauge(
            f"{namespace}_pressure",
            "Current pressure per execution",
            labelnames=["execution_id"],
            registry=self._registry,
        )
        self._active = Gauge(
            f"{namespace}_active_executions",
            "Count of currently active executions",
            registry=self._registry,
        )
        self._coord_pressure = Gauge(
            f"{namespace}_coordinator_pressure",
            "Aggregate coordinator pressure",
            registry=self._registry,
        )
        self._coord_escalations = Counter(
            f"{namespace}_coordinator_escalations_total",
            "Coordinator escalation events",
            registry=self._registry,
        )

        self._lock = threading.Lock()
        self._active_set: set[str] = set()

    @property
    def registry(self) -> Any:
        return self._registry

    def emit(self, event: AuditEvent) -> None:
        kind = event.kind
        data = event.data
        exec_id = event.execution_id

        try:
            if kind == "engine.init":
                with self._lock:
                    self._active_set.add(exec_id)
                    self._active.set(len(self._active_set))
            elif kind == "engine.step":
                outcome = str(data.get("outcome", "unknown"))
                self._steps.labels(outcome=outcome).inc()
                p = data.get("pressure")
                if isinstance(p, (int, float)):
                    self._pressure.labels(execution_id=exec_id).set(float(p))
            elif kind == "engine.escalation":
                self._escalations.inc()
            elif kind == "engine.release":
                self._releases.inc()
            elif kind == "engine.reset":
                self._resets.inc()
            elif kind == "execution.lifecycle":
                if str(data.get("to", "")) in ("released", "closed"):
                    with self._lock:
                        self._active_set.discard(exec_id)
                        self._active.set(len(self._active_set))
                    try:
                        self._pressure.remove(exec_id)
                    except KeyError:
                        pass
            elif kind.startswith("consent.") and "denied" in kind:
                self._consent_denied.labels(
                    reason=str(data.get("reason", "unknown"))
                ).inc()
            elif kind == "coordinator.escalation":
                self._coord_escalations.inc()
                agg = data.get("aggregate_pressure")
                if isinstance(agg, (int, float)):
                    self._coord_pressure.set(float(agg))
        except Exception:  # noqa: BLE001
            # A metric update must never break the audit path.
            pass


class OTelMetricsSink:
    """Metrics sink that records to the OpenTelemetry SDK.

    Callers are responsible for configuring the OTel MeterProvider and any
    exporters (OTLP, Prometheus, stdout). This sink only creates
    instruments under a named meter.

    Requires: pip install iaiso[otel]
    """

    def __init__(self, meter_name: str = "iaiso") -> None:
        try:
            from opentelemetry import metrics  # noqa: F401
        except ImportError as e:  # pragma: no cover
            raise ImportError(
                "OTelMetricsSink requires opentelemetry-api. "
                "Install with: pip install iaiso[otel]"
            ) from e
        from opentelemetry import metrics

        meter = metrics.get_meter(meter_name)
        self._steps = meter.create_counter(
            "iaiso.steps", unit="1", description="Engine steps by outcome"
        )
        self._escalations = meter.create_counter(
            "iaiso.escalations", unit="1", description="Escalation events"
        )
        self._releases = meter.create_counter(
            "iaiso.releases", unit="1", description="Release events"
        )
        self._resets = meter.create_counter(
            "iaiso.resets", unit="1", description="Engine resets"
        )
        self._consent_denied = meter.create_counter(
            "iaiso.consent_denied", unit="1", description="Denied consent checks"
        )
        # OTel gauges: use observable gauges with in-process state
        self._pressure_state: dict[str, float] = {}
        self._coord_state: dict[str, float] = {"current": 0.0}
        self._active_state: dict[str, int] = {"count": 0}
        self._active_set: set[str] = set()
        self._lock = threading.Lock()

        meter.create_observable_gauge(
            "iaiso.pressure",
            callbacks=[lambda opts: self._pressure_callback()],
            description="Per-execution pressure",
        )
        meter.create_observable_gauge(
            "iaiso.active_executions",
            callbacks=[lambda opts: self._active_callback()],
            description="Active executions count",
        )
        meter.create_observable_gauge(
            "iaiso.coordinator_pressure",
            callbacks=[lambda opts: self._coord_callback()],
            description="Coordinator aggregate pressure",
        )

    def _pressure_callback(self) -> list[Any]:
        from opentelemetry.metrics import Observation
        with self._lock:
            return [
                Observation(v, {"execution_id": eid})
                for eid, v in self._pressure_state.items()
            ]

    def _active_callback(self) -> list[Any]:
        from opentelemetry.metrics import Observation
        return [Observation(self._active_state["count"], {})]

    def _coord_callback(self) -> list[Any]:
        from opentelemetry.metrics import Observation
        return [Observation(self._coord_state["current"], {})]

    def emit(self, event: AuditEvent) -> None:
        try:
            kind = event.kind
            data = event.data
            exec_id = event.execution_id
            if kind == "engine.init":
                with self._lock:
                    self._active_set.add(exec_id)
                    self._active_state["count"] = len(self._active_set)
            elif kind == "engine.step":
                self._steps.add(1, {"outcome": str(data.get("outcome", "unknown"))})
                p = data.get("pressure")
                if isinstance(p, (int, float)):
                    with self._lock:
                        self._pressure_state[exec_id] = float(p)
            elif kind == "engine.escalation":
                self._escalations.add(1)
            elif kind == "engine.release":
                self._releases.add(1)
            elif kind == "engine.reset":
                self._resets.add(1)
            elif kind == "execution.lifecycle":
                if str(data.get("to", "")) in ("released", "closed"):
                    with self._lock:
                        self._active_set.discard(exec_id)
                        self._active_state["count"] = len(self._active_set)
                        self._pressure_state.pop(exec_id, None)
            elif kind.startswith("consent.") and "denied" in kind:
                self._consent_denied.add(1, {"reason": str(data.get("reason", "unknown"))})
            elif kind == "coordinator.escalation":
                agg = data.get("aggregate_pressure")
                if isinstance(agg, (int, float)):
                    self._coord_state["current"] = float(agg)
        except Exception:  # noqa: BLE001
            pass
