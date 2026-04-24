"""Sumo Logic HTTP Source audit sink.

Forwards IAIso audit events to a Sumo Logic HTTP Source endpoint. Sumo
accepts newline-delimited JSON with no authentication header — the
unique collector URL itself is the credential, so it must be treated
as a secret.

Docs: https://help.sumologic.com/docs/send-data/hosted-collectors/http-source/

Wire format:
    One JSON object per event, separated by newlines. Sumo parses each
    line as a log record. Optional `X-Sumo-Category`, `X-Sumo-Name`,
    and `X-Sumo-Host` headers customize how events appear in Sumo.

Verification Required Before Production:
    Tested against a mock HTTP server. End-to-end verification needs a
    real Sumo Logic HTTP Source, confirmation events parse with the
    expected field extraction, and load testing at your event rate.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from iaiso.audit import AuditEvent
from iaiso.audit.webhook import WebhookConfig, WebhookSink


@dataclass
class SumoLogicConfig:
    """Configuration for the Sumo Logic HTTP Source sink.

    Attributes:
        url: The HTTP Source collector URL (treat as a secret).
        source_category: Populates the `_sourceCategory` metadata. Typically
            used in Sumo search: `_sourceCategory=iaiso/prod`.
        source_name: Populates `_sourceName`.
        source_host: Populates `_sourceHost`.
        timeout_seconds: Per-request timeout.
        max_queue_size: In-memory event queue limit.
        batch_size: Events per HTTP request.
        verify_tls: Verify TLS certificates.
    """

    url: str
    source_category: str = "iaiso/audit"
    source_name: str | None = None
    source_host: str | None = None
    timeout_seconds: float = 5.0
    max_queue_size: int = 10000
    batch_size: int = 100
    verify_tls: bool = True


def sumo_logic_payload(event: AuditEvent) -> dict[str, Any]:
    """Translate an IAIso event to Sumo's preferred JSON shape."""
    return {
        "timestamp": event.timestamp,
        "kind": event.kind,
        "execution_id": event.execution_id,
        "schema_version": event.schema_version,
        **event.data,
    }


class SumoLogicSink(WebhookSink):
    """Audit sink that forwards events to Sumo Logic."""

    def __init__(self, cfg: SumoLogicConfig) -> None:
        self._sumo_cfg = cfg
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if cfg.source_category:
            headers["X-Sumo-Category"] = cfg.source_category
        if cfg.source_name:
            headers["X-Sumo-Name"] = cfg.source_name
        if cfg.source_host:
            headers["X-Sumo-Host"] = cfg.source_host
        super().__init__(WebhookConfig(
            url=cfg.url,
            headers=headers,
            timeout_seconds=cfg.timeout_seconds,
            max_queue_size=cfg.max_queue_size,
            batch_size=cfg.batch_size,
            verify_tls=cfg.verify_tls,
        ))

    def _flush(self, events: list[AuditEvent]) -> None:  # type: ignore[override]
        # Sumo HTTP Source: newline-delimited JSON. One line per event.
        body = "\n".join(
            json.dumps(sumo_logic_payload(e), sort_keys=True)
            for e in events
        ).encode("utf-8")

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
