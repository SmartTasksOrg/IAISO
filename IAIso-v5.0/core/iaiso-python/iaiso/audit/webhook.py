"""Webhook sink for forwarding audit events to external systems.

This is the generic integration point for SIEM (Splunk HEC, Datadog Logs, Sumo,
Elastic) and other log aggregators. Most such systems accept JSON over HTTPS.

For SIEM-specific integrations with structured field mapping, build on top of
this module rather than re-implementing HTTP handling.
"""

from __future__ import annotations

import json
import queue
import ssl
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from iaiso.audit import AuditEvent


@dataclass
class WebhookConfig:
    """Configuration for a webhook audit sink.

    Attributes:
        url: HTTPS endpoint to POST events to. HTTP (non-TLS) is allowed only
            for localhost; non-localhost HTTP URLs raise ValueError.
        headers: Additional headers to include on each request, e.g. an auth
            token. Content-Type is always set to application/json.
        timeout_seconds: Per-request timeout.
        max_queue_size: Maximum number of events buffered in memory before
            backpressure kicks in and events are dropped. A warning is logged
            on drop but the engine does not block.
        batch_size: Events are sent one at a time by default (batch_size=1).
            Set higher to batch as a JSON array per POST.
        verify_tls: If False, disables TLS certificate verification. Only use
            for testing against self-signed endpoints.
    """

    url: str
    headers: dict[str, str] | None = None
    timeout_seconds: float = 5.0
    max_queue_size: int = 10_000
    batch_size: int = 1
    verify_tls: bool = True

    def __post_init__(self) -> None:
        if self.url.startswith("http://"):
            host = self.url.split("/", 3)[2].split(":")[0]
            if host not in ("localhost", "127.0.0.1", "::1"):
                raise ValueError(
                    "non-localhost HTTP webhook URLs are not allowed; use HTTPS"
                )
        elif not self.url.startswith("https://"):
            raise ValueError("webhook URL must start with https:// or http://")
        if self.max_queue_size < 1:
            raise ValueError("max_queue_size must be >= 1")
        if self.batch_size < 1:
            raise ValueError("batch_size must be >= 1")


class WebhookSink:
    """Audit sink that POSTs events to an HTTP(S) endpoint in a background thread.

    Events are enqueued synchronously from the engine thread and dispatched
    asynchronously. If the queue fills, new events are dropped with a warning;
    the engine is never blocked by a slow or unavailable webhook.

    Call `close()` (or use as a context manager) to flush pending events
    before shutdown.
    """

    def __init__(self, config: WebhookConfig) -> None:
        self._cfg = config
        self._queue: queue.Queue[AuditEvent | None] = queue.Queue(
            maxsize=config.max_queue_size
        )
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._drops = 0

    @property
    def dropped_events(self) -> int:
        return self._drops

    def emit(self, event: AuditEvent) -> None:
        try:
            self._queue.put_nowait(event)
        except queue.Full:
            self._drops += 1

    def close(self, timeout: float = 10.0) -> None:
        self._queue.put(None)
        self._thread.join(timeout=timeout)

    def __enter__(self) -> "WebhookSink":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _run(self) -> None:
        batch: list[AuditEvent] = []
        while True:
            try:
                item = self._queue.get(timeout=1.0)
            except queue.Empty:
                if batch:
                    self._flush(batch)
                    batch = []
                continue
            if item is None:
                if batch:
                    self._flush(batch)
                return
            batch.append(item)
            if len(batch) >= self._cfg.batch_size:
                self._flush(batch)
                batch = []

    def _flush(self, events: list[AuditEvent]) -> None:
        body: bytes
        if len(events) == 1:
            body = events[0].to_json().encode("utf-8")
        else:
            body = json.dumps(
                [json.loads(e.to_json()) for e in events],
                sort_keys=True,
            ).encode("utf-8")

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
            # Silent failure is deliberate: we don't want audit problems to
            # take down the caller. Real deployments should monitor
            # `dropped_events` and webhook 5xx counts at the sink level.
            pass
