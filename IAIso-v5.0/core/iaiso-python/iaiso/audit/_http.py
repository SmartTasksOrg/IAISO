"""Shared HTTP delivery for the network audit sinks."""

from __future__ import annotations

import logging
import ssl
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger("iaiso")


def deliver(sink: Any, req: urllib.request.Request, timeout: float,
            context: ssl.SSLContext | None) -> bool:
    """POST one batch. Never raises into the caller: audit trouble must not
    take the agent down. But a failure is no longer silent: it is counted on
    `sink.delivery_failures` and logged (first failure, then every 100th)."""
    if not req.full_url.startswith(("https://", "http://")):
        _failed(sink, ValueError(f"refusing non-http(s) audit URL {req.full_url[:40]!r}"))
        return False
    try:
        # Scheme is checked above, so this cannot open file:// or other schemes.
        with urllib.request.urlopen(req, timeout=timeout, context=context):  # nosec B310  # nosemgrep: urlopen-non-literal
            pass
        return True
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        _failed(sink, exc)
        return False


def _failed(sink: Any, exc: BaseException) -> None:
    n = getattr(sink, "delivery_failures", 0) + 1
    if hasattr(sink, "__dict__"):
        sink.delivery_failures = n
    if n == 1 or n % 100 == 0:
        logger.warning("iaiso.audit: %s delivery failed (%d so far): %s",
                       type(sink).__name__, n, exc)
