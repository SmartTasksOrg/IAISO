"""Network audit sinks: failures are counted and logged, not silently dropped
(I-16), and only http(s) URLs are ever opened (bandit B310)."""

from __future__ import annotations

import logging
import socket
import urllib.request

from iaiso.audit import AuditEvent
from iaiso.audit._http import deliver
from iaiso.audit.webhook import WebhookConfig, WebhookSink


class Sink:
    pass


def _closed_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_delivery_failure_is_counted_and_logged(caplog):
    sink = Sink()
    req = urllib.request.Request(f"http://127.0.0.1:{_closed_port()}/x", data=b"{}", method="POST")
    with caplog.at_level(logging.WARNING, logger="iaiso"):
        assert deliver(sink, req, 1.0, None) is False
        assert deliver(sink, req, 1.0, None) is False
    assert sink.delivery_failures == 2
    assert sum("delivery failed" in r.message for r in caplog.records) == 1  # first only


def test_non_http_scheme_is_never_opened(tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("do not read")
    sink = Sink()
    req = urllib.request.Request(secret.as_uri())
    assert deliver(sink, req, 1.0, None) is False
    assert sink.delivery_failures == 1


def test_webhook_sink_counts_failures_end_to_end():
    s = WebhookSink(WebhookConfig(url=f"http://127.0.0.1:{_closed_port()}/hook", timeout_seconds=0.5))
    s.emit(AuditEvent(execution_id="e", kind="engine.step", timestamp=0.0, data={}))
    s.close(timeout=5.0)
    assert getattr(s, "delivery_failures", 0) >= 1
