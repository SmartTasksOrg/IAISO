"""New Relic Logs API audit sink.

Forwards IAIso audit events to the New Relic Logs API. The API accepts
either a single JSON object, an array of objects, or a gzipped-array.
We use the array form for batching.

Docs:
    US endpoint:  https://log-api.newrelic.com/log/v1
    EU endpoint:  https://log-api.eu.newrelic.com/log/v1
Auth:  `Api-Key: <INGEST_LICENSE_KEY>` header.

Wire format:
    [
      {
        "timestamp": 1700000000123,     # epoch milliseconds
        "message":   "engine.step",     # short description
        "logtype":   "iaiso",
        "attributes": { ... event data ... }
      },
      ...
    ]

Verification Required Before Production:
    Tested against a mock HTTP server. End-to-end verification needs a
    New Relic account, confirmation that events appear in Logs UI under
    the expected logtype, and that attribute extraction works.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from iaiso.audit import AuditEvent
from iaiso.audit.webhook import WebhookConfig, WebhookSink


@dataclass
class NewRelicConfig:
    """Configuration for the New Relic Logs sink.

    Attributes:
        url: Logs API endpoint. US default:
            `https://log-api.newrelic.com/log/v1`
            EU default:
            `https://log-api.eu.newrelic.com/log/v1`
        api_key: Ingest license key (not a user key).
        logtype: Value for the `logtype` field, used for pipeline routing
            in New Relic. Defaults to "iaiso".
        service_name: Optional value for the `service.name` attribute,
            useful for tying logs to APM data.
    """

    url: str = "https://log-api.newrelic.com/log/v1"
    api_key: str = ""
    logtype: str = "iaiso"
    service_name: str | None = None
    timeout_seconds: float = 5.0
    max_queue_size: int = 10000
    batch_size: int = 100
    verify_tls: bool = True


def new_relic_payload(event: AuditEvent, cfg: NewRelicConfig) -> dict[str, Any]:
    """Translate an IAIso event to a New Relic log record."""
    attrs: dict[str, Any] = {
        "iaiso.execution_id": event.execution_id,
        "iaiso.kind": event.kind,
        "iaiso.schema_version": event.schema_version,
    }
    # Prefix event data attributes with `iaiso.` so they don't collide with
    # other attributes in the user's account.
    for k, v in event.data.items():
        attrs[f"iaiso.{k}"] = v
    if cfg.service_name:
        attrs["service.name"] = cfg.service_name
    return {
        # New Relic expects epoch ms, not seconds.
        "timestamp": int(event.timestamp * 1000),
        "message": event.kind,
        "logtype": cfg.logtype,
        "attributes": attrs,
    }


class NewRelicSink(WebhookSink):
    """Audit sink that forwards events to New Relic Logs."""

    def __init__(self, cfg: NewRelicConfig) -> None:
        if not cfg.api_key:
            raise ValueError("NewRelicConfig.api_key is required")
        self._nr_cfg = cfg
        super().__init__(WebhookConfig(
            url=cfg.url,
            headers={
                "Api-Key": cfg.api_key,
                "Content-Type": "application/json",
            },
            timeout_seconds=cfg.timeout_seconds,
            max_queue_size=cfg.max_queue_size,
            batch_size=cfg.batch_size,
            verify_tls=cfg.verify_tls,
        ))

    def _flush(self, events: list[AuditEvent]) -> None:  # type: ignore[override]
        # New Relic accepts a JSON array of log records.
        payload = [new_relic_payload(e, self._nr_cfg) for e in events]
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
