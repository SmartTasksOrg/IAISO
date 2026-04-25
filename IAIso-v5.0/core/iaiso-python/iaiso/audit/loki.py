"""Grafana Loki audit sink.

Forwards IAIso audit events to a Grafana Loki push endpoint. Loki's wire
format differs from most logging APIs: events are grouped into "streams"
identified by a label set, and each stream carries an array of
[timestamp_ns, line] tuples.

Docs: https://grafana.com/docs/loki/latest/reference/loki-http-api/#push-log-entries-to-loki

Wire format:
    {
      "streams": [
        {
          "stream": {"app": "iaiso", "kind": "engine.step"},
          "values": [
            ["1700000000123000000", "<JSON line>"],
            ["1700000000124000000", "<JSON line>"]
          ]
        }
      ]
    }

Grouping strategy:
    We group events in a batch by (execution_id, kind) so operators can
    filter by either label in LogQL. If the batch spans many executions,
    this may produce many small streams — acceptable for typical loads.

Auth:
    Loki itself is often unauthenticated behind a reverse proxy. Grafana
    Cloud uses HTTP Basic auth: `username` is the user ID, `password` is
    an API token.

Verification Required Before Production:
    Tested against a mock HTTP server. End-to-end verification needs a
    real Loki (self-hosted or Grafana Cloud), confirmation that streams
    appear in Explore with the expected labels, and cardinality review
    — the (execution_id, kind) label scheme can create high cardinality
    for large fleets; see `use_execution_label` below.
"""

from __future__ import annotations

import base64
import collections
import json
from dataclasses import dataclass, field
from typing import Any

from iaiso.audit import AuditEvent
from iaiso.audit.webhook import WebhookConfig, WebhookSink


@dataclass
class LokiConfig:
    """Configuration for the Grafana Loki sink.

    Attributes:
        url: The push endpoint. Typically
            `http://<loki-host>/loki/api/v1/push` or
            `https://logs-prod-XXX.grafana.net/loki/api/v1/push` for
            Grafana Cloud.
        username: For HTTP Basic auth (Grafana Cloud, optional Loki).
        password: For HTTP Basic auth.
        static_labels: Labels attached to every stream. Keep LOW
            cardinality — Loki struggles with high-cardinality labels.
            Example: {"app": "iaiso", "env": "prod"}.
        use_execution_label: If True, adds `execution_id` as a label.
            WARNING: high cardinality. Leave off for large fleets;
            execution_id is available in the log line itself.
    """

    url: str
    username: str | None = None
    password: str | None = None
    static_labels: dict[str, str] = field(default_factory=lambda: {"app": "iaiso"})
    use_execution_label: bool = False
    timeout_seconds: float = 5.0
    max_queue_size: int = 10000
    batch_size: int = 200
    verify_tls: bool = True


def _stream_key(event: AuditEvent, cfg: LokiConfig) -> dict[str, str]:
    """Build the label set for this event's stream."""
    labels = dict(cfg.static_labels)
    labels["kind"] = event.kind
    if cfg.use_execution_label:
        labels["execution_id"] = event.execution_id
    return labels


def _log_line(event: AuditEvent) -> str:
    """Serialize the full event as a single JSON line (the log body)."""
    return json.dumps({
        "execution_id": event.execution_id,
        "kind": event.kind,
        "schema_version": event.schema_version,
        **event.data,
    }, sort_keys=True)


def loki_payload(events: list[AuditEvent], cfg: LokiConfig) -> dict[str, Any]:
    """Group events into Loki streams."""
    streams: dict[tuple[tuple[str, str], ...], list[list[str]]] = collections.defaultdict(list)
    for e in events:
        labels = _stream_key(e, cfg)
        key = tuple(sorted(labels.items()))
        # Loki timestamps are strings of nanoseconds since epoch.
        ts_ns = str(int(e.timestamp * 1_000_000_000))
        streams[key].append([ts_ns, _log_line(e)])
    return {
        "streams": [
            {"stream": dict(key), "values": values}
            for key, values in streams.items()
        ]
    }


class LokiSink(WebhookSink):
    """Audit sink that forwards events to Grafana Loki."""

    def __init__(self, cfg: LokiConfig) -> None:
        self._loki_cfg = cfg
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if cfg.username and cfg.password:
            token = base64.b64encode(
                f"{cfg.username}:{cfg.password}".encode()
            ).decode()
            headers["Authorization"] = f"Basic {token}"
        super().__init__(WebhookConfig(
            url=cfg.url,
            headers=headers,
            timeout_seconds=cfg.timeout_seconds,
            max_queue_size=cfg.max_queue_size,
            batch_size=cfg.batch_size,
            verify_tls=cfg.verify_tls,
        ))

    def _flush(self, events: list[AuditEvent]) -> None:  # type: ignore[override]
        payload = loki_payload(events, self._loki_cfg)
        body = json.dumps(payload, sort_keys=True).encode("utf-8")

        import ssl
        import urllib.error
        import urllib.request
        req = urllib.request.Request(
            self._cfg.url,
            data=body,
            method="POST",
            headers=self._cfg.headers or {},
        )
        ctx: ssl.SSLContext | None = None
        if self._cfg.url.startswith("https://") and not self._cfg.verify_tls:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        try:
            with urllib.request.urlopen(
                req, timeout=self._cfg.timeout_seconds, context=ctx
            ):
                pass
        except (urllib.error.URLError, TimeoutError):
            pass
