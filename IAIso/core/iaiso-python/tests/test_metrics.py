"""Tests for the metrics subsystem."""

from __future__ import annotations

import pytest

from iaiso import BoundedExecution, PressureConfig
from iaiso.audit import AuditEvent
from iaiso.metrics import InMemoryMetricsSink


def _event(kind: str, execution_id: str = "e1", **data: object) -> AuditEvent:
    return AuditEvent(execution_id=execution_id, kind=kind,
                      timestamp=0.0, data=data)


def test_in_memory_counts_steps_by_outcome() -> None:
    sink = InMemoryMetricsSink()
    sink.emit(_event("engine.step", outcome="running", pressure=0.1))
    sink.emit(_event("engine.step", outcome="running", pressure=0.2))
    sink.emit(_event("engine.step", outcome="escalated", pressure=0.5))
    snap = sink.snapshot()
    counters = snap.counters["iaiso_steps_total"]
    assert counters[(("outcome", "running"),)] == 2
    assert counters[(("outcome", "escalated"),)] == 1


def test_in_memory_tracks_pressure_gauge() -> None:
    sink = InMemoryMetricsSink()
    sink.emit(_event("engine.step", execution_id="e1", pressure=0.3))
    sink.emit(_event("engine.step", execution_id="e1", pressure=0.7))
    sink.emit(_event("engine.step", execution_id="e2", pressure=0.2))
    snap = sink.snapshot()
    assert snap.gauges["iaiso_pressure"][(("execution_id", "e1"),)] == 0.7
    assert snap.gauges["iaiso_pressure"][(("execution_id", "e2"),)] == 0.2


def test_in_memory_counts_escalations_and_releases() -> None:
    sink = InMemoryMetricsSink()
    for _ in range(3):
        sink.emit(_event("engine.escalation"))
    sink.emit(_event("engine.release"))
    snap = sink.snapshot()
    assert snap.counters["iaiso_escalations_total"][()] == 3
    assert snap.counters["iaiso_releases_total"][()] == 1


def test_in_memory_tracks_active_executions() -> None:
    sink = InMemoryMetricsSink()
    sink.emit(_event("engine.init", execution_id="e1"))
    sink.emit(_event("engine.init", execution_id="e2"))
    snap = sink.snapshot()
    assert snap.gauges["iaiso_active_executions"][()] == 2
    sink.emit(_event("execution.lifecycle", execution_id="e1",
                     to="released"))
    snap = sink.snapshot()
    assert snap.gauges["iaiso_active_executions"][()] == 1


def test_prometheus_exposition_format() -> None:
    sink = InMemoryMetricsSink()
    sink.emit(_event("engine.step", outcome="running", pressure=0.5))
    sink.emit(_event("engine.escalation"))
    text = sink.render_prometheus()
    assert "# TYPE iaiso_steps_total counter" in text
    assert 'iaiso_steps_total{outcome="running"} 1' in text
    assert "# TYPE iaiso_escalations_total counter" in text
    assert "iaiso_escalations_total 1" in text


def test_prometheus_escapes_label_values() -> None:
    sink = InMemoryMetricsSink()
    sink.emit(_event("consent.denied.scope",
                     reason='user said "no"'))
    text = sink.render_prometheus()
    # Double-quote escaped as \"
    assert r'reason="user said \"no\""' in text


def test_unknown_event_kinds_ignored() -> None:
    sink = InMemoryMetricsSink()
    sink.emit(_event("completely.unknown.kind", some="data"))
    snap = sink.snapshot()
    # No crash, no spurious metrics
    assert snap.counters == {}
    assert snap.gauges == {}


def test_integration_with_bounded_execution() -> None:
    sink = InMemoryMetricsSink()
    with BoundedExecution.start(
        config=PressureConfig(token_coefficient=0.1,
                              dissipation_per_step=0.0),
        audit_sink=sink,
    ) as exec_:
        for _ in range(5):
            exec_.record_step(tokens=1000)
    snap = sink.snapshot()
    # We should see 5 step events in the counter
    total_steps = sum(snap.counters["iaiso_steps_total"].values())
    assert total_steps == 5


def test_prometheus_sink_requires_library() -> None:
    """If prometheus_client isn't available we should get a clear ImportError
    at construction, not a surprise AttributeError later."""
    try:
        import prometheus_client  # noqa: F401
    except ImportError:
        from iaiso.metrics import PrometheusMetricsSink
        with pytest.raises(ImportError, match="prometheus_client"):
            PrometheusMetricsSink()
    else:
        pytest.skip("prometheus_client is installed; skipping negative test")


def test_prometheus_sink_when_library_available() -> None:
    """Exercise the real PrometheusMetricsSink if prometheus_client installed."""
    try:
        from prometheus_client import CollectorRegistry, generate_latest
    except ImportError:
        pytest.skip("prometheus_client not installed")
    from iaiso.metrics import PrometheusMetricsSink

    registry = CollectorRegistry()
    sink = PrometheusMetricsSink(registry=registry)
    sink.emit(_event("engine.step", outcome="running", pressure=0.4))
    sink.emit(_event("engine.escalation"))
    output = generate_latest(registry).decode()
    assert "iaiso_steps_total" in output
    assert "iaiso_escalations_total" in output
