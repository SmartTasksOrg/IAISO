"""Datadog Logs audit sink.

Forwards IAIso audit events to Datadog's Logs intake API. See:
    https://docs.datadoghq.com/api/latest/logs/#send-logs

Wire format: a JSON array of log objects. Datadog expects specific
reserved attribute names (`ddsource`, `service`, `host`, `ddtags`,
`message`). Other fields go in the top-level log object and are
auto-indexed by Datadog's log processing pipeline.

Auth: "DD-API-KEY: <api-key>" header.

Verification Required Before Production:
    This sink has been tested against a mock HTTP server that verifies
    request shape. End-to-end verification requires:
    - A Datadog account with Logs enabled and an API key.
    - Confirmation that events appear in the Datadog Logs UI within
      the expected latency (typically <30 seconds).
    - Configuration of facets and reserved attributes in Datadog for
      efficient search on IAIso-specific fields.
    - Verification that your Datadog intake endpoint matches your
      region (US1, US3, US5, EU, etc.) — use `http-intake.logs.<region>.datadoghq.com`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from iaiso.audit import AuditEvent
from iaiso.audit.webhook import WebhookConfig, WebhookSink


@dataclass
class DatadogLogsConfig:
    """Configuration for the Datadog Logs sink.

    Attributes:
        intake_url: Full Datadog Logs intake URL. Defaults to the US1
            endpoint. Use your region's endpoint for lower latency and
            data residency compliance:
                US1:  https://http-intake.logs.datadoghq.com/api/v2/logs
                US3:  https://http-intake.logs.us3.datadoghq.com/api/v2/logs
                US5:  https://http-intake.logs.us5.datadoghq.com/api/v2/logs
                EU1:  https://http-intake.logs.datadoghq.eu/api/v2/logs
                AP1:  https://http-intake.logs.ap1.datadoghq.com/api/v2/logs
        api_key: Datadog API key (NOT an application key).
        service: Datadog `service` tag. Defaults to "iaiso".
        ddsource: Datadog `ddsource` tag. Defaults to "iaiso". This
            controls which pipeline Datadog uses to parse the log.
        env: Optional Datadog `env` tag for environment tagging.
        host: Optional host field.
        tags: Additional Datadog tags as a list of "key:value" strings,
            included as `ddtags` on each event.
        batch_size: How many events per request. Datadog accepts up to
            1000 events or 5 MB per request, whichever is lower.
        timeout_seconds: HTTP timeout.
        max_queue_size: Max queued events before drops.
        verify_tls: Disable only for testing.
    """

    api_key: str
    intake_url: str = "https://http-intake.logs.datadoghq.com/api/v2/logs"
    service: str = "iaiso"
    ddsource: str = "iaiso"
    env: str | None = None
    host: str | None = None
    tags: list[str] | None = None
    batch_size: int = 100
    timeout_seconds: float = 10.0
    max_queue_size: int = 10_000
    verify_tls: bool = True


def datadog_log_payload(
    event: AuditEvent,
    cfg: DatadogLogsConfig,
) -> dict[str, Any]:
    """Map an IAIso AuditEvent to a Datadog log object."""
    ddtags_parts = [f"event_kind:{event.kind}"]
    if cfg.env is not None:
        ddtags_parts.append(f"env:{cfg.env}")
    if cfg.tags:
        ddtags_parts.extend(cfg.tags)

    payload: dict[str, Any] = {
        "message": f"{event.kind} execution={event.execution_id}",
        "ddsource": cfg.ddsource,
        "service": cfg.service,
        "ddtags": ",".join(ddtags_parts),
        "timestamp": int(event.timestamp * 1000),  # Datadog wants ms since epoch
        "iaiso": {
            "kind": event.kind,
            "execution_id": event.execution_id,
            "schema_version": event.schema_version,
            "data": event.data,
        },
    }
    if cfg.host is not None:
        payload["host"] = cfg.host
    return payload


class DatadogLogsSink(WebhookSink):
    """Audit sink that forwards events to Datadog Logs."""

    def __init__(self, cfg: DatadogLogsConfig) -> None:
        self._dd_cfg = cfg
        super().__init__(WebhookConfig(
            url=cfg.intake_url,
            headers={
                "DD-API-KEY": cfg.api_key,
                "Content-Type": "application/json",
            },
            timeout_seconds=cfg.timeout_seconds,
            max_queue_size=cfg.max_queue_size,
            batch_size=cfg.batch_size,
            verify_tls=cfg.verify_tls,
        ))

    def _flush(self, events: list[AuditEvent]) -> None:  # type: ignore[override]
        payloads = [datadog_log_payload(e, self._dd_cfg) for e in events]
        body = json.dumps(payloads, sort_keys=True).encode("utf-8")

        import ssl
        import urllib.error
        import urllib.request
        req = urllib.request.Request(
            self._cfg.url,
            data=body,
            method="POST",
            headers={**(self._cfg.headers or {})},
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
