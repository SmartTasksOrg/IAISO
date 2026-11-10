"""Tests for the SIEM sinks (Splunk, Datadog, Elastic).

These tests verify the wire format each sink produces matches the
vendor's documented spec. They use a local HTTP server to capture
the actual bytes sent.

End-to-end verification against real Splunk/Datadog/Elastic instances
is REQUIRED before production deployment; these tests cover the parts
we can verify offline.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest

from iaiso.audit import AuditEvent
from iaiso.audit.datadog import DatadogLogsConfig, DatadogLogsSink, datadog_log_payload
from iaiso.audit.elastic import ElasticConfig, ElasticSink, elastic_bulk_body
from iaiso.audit.splunk import SplunkHECConfig, SplunkHECSink, splunk_hec_payload


class CaptureHandler(BaseHTTPRequestHandler):
    captured: list[dict[str, Any]] = []

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""
        self.captured.append({
            "path": self.path,
            "headers": dict(self.headers),
            "body": body,
        })
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def log_message(self, *args: Any) -> None:
        # Silence test output.
        return


@pytest.fixture
def capture_server() -> Any:
    CaptureHandler.captured = []
    server = HTTPServer(("127.0.0.1", 0), CaptureHandler)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}", CaptureHandler.captured
    server.shutdown()
    server.server_close()


def _event(kind: str = "engine.step") -> AuditEvent:
    return AuditEvent(
        execution_id="exec-test",
        kind=kind,
        timestamp=1700000000.123,
        data={"pressure": 0.42, "tokens": 500},
    )


# -- Splunk HEC -------------------------------------------------------------

def test_splunk_payload_shape() -> None:
    cfg = SplunkHECConfig(
        url="http://localhost/services/collector/event",
        token="tok",
        index="main",
        host="h1",
    )
    payload = splunk_hec_payload(_event(), cfg)
    assert payload["time"] == pytest.approx(1700000000.123)
    assert payload["source"] == "iaiso"
    assert payload["sourcetype"] == "iaiso:audit"
    assert payload["index"] == "main"
    assert payload["host"] == "h1"
    assert payload["event"]["kind"] == "engine.step"
    assert payload["event"]["execution_id"] == "exec-test"
    assert payload["event"]["pressure"] == pytest.approx(0.42)


def test_splunk_omits_optional_fields_when_unset() -> None:
    cfg = SplunkHECConfig(url="http://localhost/x", token="tok")
    payload = splunk_hec_payload(_event(), cfg)
    assert "index" not in payload
    assert "host" not in payload


def test_splunk_sink_sends_auth_header(capture_server: Any) -> None:
    url, captured = capture_server
    cfg = SplunkHECConfig(url=url, token="my-hec-token", batch_size=1)
    sink = SplunkHECSink(cfg)
    sink.emit(_event())
    sink.close(timeout=3.0)
    assert len(captured) == 1
    assert captured[0]["headers"]["Authorization"] == "Splunk my-hec-token"


def test_splunk_sink_uses_newline_delimited_json(capture_server: Any) -> None:
    url, captured = capture_server
    cfg = SplunkHECConfig(url=url, token="t", batch_size=3)
    sink = SplunkHECSink(cfg)
    for i in range(3):
        sink.emit(_event(f"e{i}"))
    sink.close(timeout=3.0)
    assert len(captured) == 1
    # Splunk HEC batch is newline-delimited JSON objects, NOT an array
    body = captured[0]["body"].decode()
    lines = body.strip().split("\n")
    assert len(lines) == 3
    # Each line is a valid JSON object
    for line in lines:
        obj = json.loads(line)
        assert "event" in obj


# -- Datadog Logs -----------------------------------------------------------

def test_datadog_payload_shape() -> None:
    cfg = DatadogLogsConfig(api_key="k", env="prod", host="h1", tags=["t:a"])
    payload = datadog_log_payload(_event(), cfg)
    assert payload["ddsource"] == "iaiso"
    assert payload["service"] == "iaiso"
    assert payload["host"] == "h1"
    assert payload["timestamp"] == 1700000000123  # ms
    assert "event_kind:engine.step" in payload["ddtags"]
    assert "env:prod" in payload["ddtags"]
    assert "t:a" in payload["ddtags"]
    assert payload["iaiso"]["execution_id"] == "exec-test"
    assert payload["iaiso"]["data"]["pressure"] == pytest.approx(0.42)


def test_datadog_sink_sends_api_key_header(capture_server: Any) -> None:
    url, captured = capture_server
    cfg = DatadogLogsConfig(api_key="ddkey", intake_url=url, batch_size=1)
    sink = DatadogLogsSink(cfg)
    sink.emit(_event())
    sink.close(timeout=3.0)
    headers_lower = {k.lower(): v for k, v in captured[0]["headers"].items()}
    assert headers_lower["dd-api-key"] == "ddkey"


def test_datadog_sink_sends_json_array(capture_server: Any) -> None:
    url, captured = capture_server
    cfg = DatadogLogsConfig(api_key="k", intake_url=url, batch_size=3)
    sink = DatadogLogsSink(cfg)
    for i in range(3):
        sink.emit(_event(f"e{i}"))
    sink.close(timeout=3.0)
    body = json.loads(captured[0]["body"])
    assert isinstance(body, list)
    assert len(body) == 3


# -- Elastic ----------------------------------------------------------------

def test_elastic_body_shape() -> None:
    cfg = ElasticConfig(bulk_url="http://localhost/_bulk", index="my-index")
    body = elastic_bulk_body([_event("a"), _event("b")], cfg)
    lines = body.decode().strip().split("\n")
    # Each event produces 2 lines: action header + document
    assert len(lines) == 4
    header0 = json.loads(lines[0])
    doc0 = json.loads(lines[1])
    assert header0 == {"index": {"_index": "my-index"}}
    assert doc0["kind"] == "a"
    assert doc0["execution_id"] == "exec-test"
    assert doc0["@timestamp"].startswith("2023-")  # ISO 8601 from our timestamp


def test_elastic_body_ends_with_newline() -> None:
    cfg = ElasticConfig(bulk_url="http://localhost/_bulk")
    body = elastic_bulk_body([_event()], cfg)
    # _bulk requires trailing newline
    assert body.endswith(b"\n")


def test_elastic_sink_uses_ndjson_content_type(capture_server: Any) -> None:
    url, captured = capture_server
    cfg = ElasticConfig(
        bulk_url=f"{url}/_bulk",
        auth_header="ApiKey testkey",
        batch_size=1,
    )
    sink = ElasticSink(cfg)
    sink.emit(_event())
    sink.close(timeout=3.0)
    assert captured[0]["headers"]["Content-Type"] == "application/x-ndjson"
    assert captured[0]["headers"]["Authorization"] == "ApiKey testkey"


def test_elastic_sink_batches_in_bulk_format(capture_server: Any) -> None:
    url, captured = capture_server
    cfg = ElasticConfig(bulk_url=f"{url}/_bulk", batch_size=3, index="iaiso")
    sink = ElasticSink(cfg)
    for i in range(3):
        sink.emit(_event(f"e{i}"))
    sink.close(timeout=3.0)
    body = captured[0]["body"].decode()
    lines = body.strip().split("\n")
    # 3 events * 2 lines each = 6
    assert len(lines) == 6
    # Every even line is an action header
    for i in [0, 2, 4]:
        assert json.loads(lines[i]) == {"index": {"_index": "iaiso"}}
