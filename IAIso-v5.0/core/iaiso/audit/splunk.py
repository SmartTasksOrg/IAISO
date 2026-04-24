"""Splunk HTTP Event Collector (HEC) audit sink.

Forwards IAIso audit events to a Splunk HEC endpoint in the format
Splunk expects. See Splunk's HEC documentation for the wire format:
    https://docs.splunk.com/Documentation/Splunk/latest/Data/FormateventsforHTTPEventCollector

Wire format (one event per JSON object, concatenated without commas):
    {
      "time": 1700000000.123,        # unix seconds, fractional ok
      "host": "iaiso-producer",       # optional
      "source": "iaiso",              # optional
      "sourcetype": "iaiso:audit",    # optional
      "index": "main",                # optional
      "event": { ... IAIso event ... }
    }

Auth: "Authorization: Splunk <token>" header.

Verification Required Before Production:
    This sink has been tested against a mock HTTP server that verifies
    request shape. End-to-end verification requires:
    - A real Splunk HEC endpoint (Splunk Enterprise, Splunk Cloud, or
      Splunk's HEC-compatible APIs).
    - Confirmation that events land in the expected index.
    - Confirmation that the `sourcetype` renders fields correctly in
      Splunk's search interface.
    - Load testing at the event rate your deployment actually produces.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from iaiso.audit import AuditEvent
from iaiso.audit.webhook import WebhookConfig, WebhookSink


@dataclass
class SplunkHECConfig:
    """Configuration for the Splunk HEC sink.

    Attributes:
        url: The HEC endpoint, typically ending in `/services/collector/event`
            for event-mode ingestion. HTTPS required for non-localhost.
        token: The HEC token (provisioned in Splunk; a UUID-like string).
        index: Optional Splunk index name. If None, Splunk uses the
            token's default index.
        source: Value for Splunk's `source` field. Defaults to "iaiso".
        sourcetype: Value for Splunk's `sourcetype` field. Defaults to
            "iaiso:audit". Configure field extraction for this sourcetype
            in your Splunk deployment.
        host: Optional host string. Defaults to None (Splunk will infer).
        batch_size: How many events to combine into a single HEC request.
            Splunk HEC accepts newline-concatenated events, up to the
            HEC max payload size (typically 1 MB).
        timeout_seconds: HTTP timeout per request.
        max_queue_size: Max events buffered before drops.
        verify_tls: Disable only for testing against self-signed endpoints.
    """

    url: str
    token: str
    index: str | None = None
    source: str = "iaiso"
    sourcetype: str = "iaiso:audit"
    host: str | None = None
    batch_size: int = 50
    timeout_seconds: float = 10.0
    max_queue_size: int = 10_000
    verify_tls: bool = True


def splunk_hec_payload(event: AuditEvent, cfg: SplunkHECConfig) -> dict[str, Any]:
    """Map an IAIso AuditEvent to a Splunk HEC event object.

    Exposed as a standalone function so implementations can embed IAIso
    events in larger Splunk payloads, or test the mapping without running
    a network call.
    """
    payload: dict[str, Any] = {
        "time": event.timestamp,
        "source": cfg.source,
        "sourcetype": cfg.sourcetype,
        "event": {
            "kind": event.kind,
            "execution_id": event.execution_id,
            "schema_version": event.schema_version,
            **event.data,
        },
    }
    if cfg.index is not None:
        payload["index"] = cfg.index
    if cfg.host is not None:
        payload["host"] = cfg.host
    return payload


class SplunkHECSink(WebhookSink):
    """Audit sink that forwards events to Splunk HEC.

    Subclasses the generic WebhookSink with Splunk-specific authentication
    and payload framing. Events are batched (default 50 per request) and
    serialized as newline-delimited JSON per Splunk HEC's batch format.
    """

    def __init__(self, cfg: SplunkHECConfig) -> None:
        self._splunk_cfg = cfg
        super().__init__(WebhookConfig(
            url=cfg.url,
            headers={"Authorization": f"Splunk {cfg.token}"},
            timeout_seconds=cfg.timeout_seconds,
            max_queue_size=cfg.max_queue_size,
            batch_size=cfg.batch_size,
            verify_tls=cfg.verify_tls,
        ))

    def _flush(self, events: list[AuditEvent]) -> None:  # type: ignore[override]
        # Splunk HEC batch format: newline-concatenated JSON objects, NOT
        # a JSON array. This is documented Splunk behavior and differs
        # from most JSON APIs.
        body = "\n".join(
            json.dumps(splunk_hec_payload(e, self._splunk_cfg), sort_keys=True)
            for e in events
        ).encode("utf-8")

        import ssl
        import urllib.error
        import urllib.request
        req = urllib.request.Request(
            self._cfg.url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json",
                     **(self._cfg.headers or {})},
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
            # See WebhookSink._flush for rationale on silent failure.
            pass
