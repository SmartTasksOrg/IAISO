"""Elasticsearch audit sink using the _bulk API.

Forwards IAIso audit events to an Elasticsearch cluster via the _bulk
endpoint. See:
    https://www.elastic.co/guide/en/elasticsearch/reference/current/docs-bulk.html

Wire format (NDJSON, each "action" line paired with a "source" line):
    { "index": { "_index": "iaiso-audit" } }
    { "@timestamp": "...", "kind": "engine.step", ... }
    { "index": { "_index": "iaiso-audit" } }
    { "@timestamp": "...", "kind": "engine.escalation", ... }

Auth: Supports API key auth ("Authorization: ApiKey <base64>") or
basic auth ("Authorization: Basic <base64>"). Pass whichever your
cluster requires via `auth_header`.

Verification Required Before Production:
    This sink has been tested against a mock HTTP server that verifies
    NDJSON structure. End-to-end verification requires:
    - An Elasticsearch cluster (Elastic Cloud, self-hosted, or Elastic
      Serverless).
    - Index template or component template configuring appropriate
      field mappings for IAIso fields (especially `iaiso.data.pressure`
      as a float, timestamps as date, etc.).
    - ILM (index lifecycle management) policy matching your retention
      requirements.
    - Confirmation that the cluster accepts the NDJSON format IAIso
      produces (Elasticsearch 8.x does; 7.x behavior may differ on
      edge cases).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from iaiso.audit import AuditEvent
from iaiso.audit.webhook import WebhookConfig, WebhookSink


@dataclass
class ElasticConfig:
    """Configuration for the Elasticsearch bulk sink.

    Attributes:
        bulk_url: Full URL to the Elasticsearch _bulk endpoint, e.g.
            "https://es.example.com:9200/_bulk" or a data-stream-scoped
            URL like ".../_ingest/iaiso-audit/_bulk" depending on your
            setup.
        index: Target index or data stream name. Default "iaiso-audit".
            Consider using a data stream with ILM rollover for
            production.
        auth_header: Complete value for the Authorization header, e.g.
            "ApiKey dGVzdDp0ZXN0" or "Basic dXNlcjpwYXNz". Leave None if
            the cluster is unauthenticated (rare outside dev).
        batch_size: Events per bulk request. ES _bulk supports thousands
            per request, but default 100 is a safer starting point.
        timeout_seconds: HTTP timeout.
        max_queue_size: Max queued events before drops.
        verify_tls: Disable only for testing.
    """

    bulk_url: str
    index: str = "iaiso-audit"
    auth_header: str | None = None
    batch_size: int = 100
    timeout_seconds: float = 10.0
    max_queue_size: int = 10_000
    verify_tls: bool = True


def elastic_bulk_body(events: list[AuditEvent], cfg: ElasticConfig) -> bytes:
    """Build an NDJSON body for an _bulk request.

    Exposed separately so mappings can be tested without HTTP.
    """
    lines: list[str] = []
    for event in events:
        lines.append(json.dumps({"index": {"_index": cfg.index}}))
        lines.append(json.dumps({
            "@timestamp": datetime.fromtimestamp(
                event.timestamp, tz=timezone.utc,
            ).isoformat(),
            "kind": event.kind,
            "execution_id": event.execution_id,
            "schema_version": event.schema_version,
            "iaiso": {
                "data": event.data,
            },
        }, sort_keys=True))
    # _bulk requires trailing newline
    return ("\n".join(lines) + "\n").encode("utf-8")


class ElasticSink(WebhookSink):
    """Audit sink that forwards events to Elasticsearch via _bulk."""

    def __init__(self, cfg: ElasticConfig) -> None:
        self._es_cfg = cfg
        headers: dict[str, str] = {}
        if cfg.auth_header is not None:
            headers["Authorization"] = cfg.auth_header
        # _bulk's content type is application/x-ndjson, not application/json
        super().__init__(WebhookConfig(
            url=cfg.bulk_url,
            headers=headers,
            timeout_seconds=cfg.timeout_seconds,
            max_queue_size=cfg.max_queue_size,
            batch_size=cfg.batch_size,
            verify_tls=cfg.verify_tls,
        ))

    def _flush(self, events: list[AuditEvent]) -> None:  # type: ignore[override]
        body = elastic_bulk_body(events, self._es_cfg)

        import ssl
        import urllib.error
        import urllib.request
        req = urllib.request.Request(
            self._cfg.url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/x-ndjson",
                **(self._cfg.headers or {}),
            },
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
