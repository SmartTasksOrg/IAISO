"""Tests for Sumo Logic, New Relic, and Loki audit sinks.

These tests validate wire-format correctness without hitting real
endpoints. End-to-end verification against live services is documented
as caller responsibility.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from iaiso.audit import AuditEvent
from iaiso.audit.loki import LokiConfig, loki_payload
from iaiso.audit.newrelic import NewRelicConfig, NewRelicSink, new_relic_payload
from iaiso.audit.sumologic import SumoLogicConfig, sumo_logic_payload


def _event(**overrides: Any) -> AuditEvent:
    defaults = dict(
        execution_id="e1",
        kind="engine.step",
        timestamp=1700000000.123,
        data={"pressure": 0.42, "tokens": 500},
    )
    defaults.update(overrides)
    return AuditEvent(**defaults)


# -- Sumo Logic -------------------------------------------------------------


def test_sumo_payload_shape() -> None:
    ev = _event()
    p = sumo_logic_payload(ev)
    assert p["kind"] == "engine.step"
    assert p["execution_id"] == "e1"
    assert p["timestamp"] == 1700000000.123
    assert p["pressure"] == 0.42
    assert p["tokens"] == 500


def test_sumo_payload_includes_schema_version() -> None:
    ev = _event()
    p = sumo_logic_payload(ev)
    assert "schema_version" in p


# -- New Relic --------------------------------------------------------------


def test_new_relic_payload_shape() -> None:
    cfg = NewRelicConfig(api_key="xxx", service_name="my-agent")
    ev = _event()
    p = new_relic_payload(ev, cfg)
    # New Relic wants ms, not seconds
    assert p["timestamp"] == 1700000000123
    assert p["logtype"] == "iaiso"
    assert p["message"] == "engine.step"
    # Attributes namespaced under "iaiso."
    assert p["attributes"]["iaiso.execution_id"] == "e1"
    assert p["attributes"]["iaiso.kind"] == "engine.step"
    assert p["attributes"]["iaiso.pressure"] == 0.42
    assert p["attributes"]["service.name"] == "my-agent"


def test_new_relic_requires_api_key() -> None:
    with pytest.raises(ValueError, match="api_key"):
        NewRelicSink(NewRelicConfig(api_key=""))


def test_new_relic_custom_logtype() -> None:
    cfg = NewRelicConfig(api_key="xxx", logtype="iaiso-staging")
    ev = _event()
    p = new_relic_payload(ev, cfg)
    assert p["logtype"] == "iaiso-staging"


# -- Grafana Loki -----------------------------------------------------------


def test_loki_payload_groups_by_kind() -> None:
    cfg = LokiConfig(url="http://fake", static_labels={"app": "iaiso"})
    events = [
        _event(kind="engine.step"),
        _event(kind="engine.step"),
        _event(kind="engine.escalation"),
    ]
    payload = loki_payload(events, cfg)
    streams = payload["streams"]
    # Two streams: one for engine.step (2 values), one for engine.escalation
    assert len(streams) == 2
    kinds = {s["stream"]["kind"] for s in streams}
    assert kinds == {"engine.step", "engine.escalation"}
    step_stream = next(s for s in streams if s["stream"]["kind"] == "engine.step")
    assert len(step_stream["values"]) == 2


def test_loki_timestamp_in_nanoseconds() -> None:
    cfg = LokiConfig(url="http://fake")
    payload = loki_payload([_event()], cfg)
    ts_str, _ = payload["streams"][0]["values"][0]
    # Our event timestamp is 1700000000.123 → ~1700000000123000000 ns.
    # Float precision means we accept anything within 1 microsecond.
    ts_ns = int(ts_str)
    assert abs(ts_ns - 1700000000123000000) < 1000


def test_loki_execution_label_optional() -> None:
    """When use_execution_label is off, execution_id should NOT be a label
    (but must still appear in the log line)."""
    cfg = LokiConfig(url="http://fake", use_execution_label=False)
    payload = loki_payload([_event()], cfg)
    labels = payload["streams"][0]["stream"]
    assert "execution_id" not in labels
    # Still in the line body
    _, line = payload["streams"][0]["values"][0]
    parsed = json.loads(line)
    assert parsed["execution_id"] == "e1"


def test_loki_execution_label_when_enabled() -> None:
    cfg = LokiConfig(url="http://fake", use_execution_label=True)
    payload = loki_payload([_event()], cfg)
    labels = payload["streams"][0]["stream"]
    assert labels["execution_id"] == "e1"


def test_loki_static_labels_included() -> None:
    cfg = LokiConfig(
        url="http://fake",
        static_labels={"app": "iaiso", "env": "prod", "region": "eu"},
    )
    payload = loki_payload([_event()], cfg)
    labels = payload["streams"][0]["stream"]
    assert labels["app"] == "iaiso"
    assert labels["env"] == "prod"
    assert labels["region"] == "eu"
