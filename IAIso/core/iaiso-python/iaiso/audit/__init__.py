"""Audit event emission and sinks.

Every state change in an IAIso engine emits a structured event to an AuditSink.
This is the primary integration point for downstream systems (SIEM, observability,
compliance logging). Implement the `AuditSink` protocol to forward events anywhere.

The event schema is stable and versioned. See `docs/spec/events.md` for the
wire format. Additions to the schema are backward-compatible; removals require
a major version bump.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Protocol, TextIO


SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class AuditEvent:
    """A single audit event emitted by the engine or middleware.

    Attributes:
        execution_id: Stable identifier for the execution this event belongs to.
        kind: Event type, e.g. "engine.step", "consent.verified", "middleware.call".
            The dotted prefix identifies the component; the suffix the action.
        timestamp: Unix timestamp (seconds since epoch) when the event occurred.
        data: Event-specific payload. Keys must be JSON-serializable.
        schema_version: Schema version string for the event format.
    """

    execution_id: str
    kind: str
    timestamp: float
    data: dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, default=str)


class AuditSink(Protocol):
    """A destination for audit events. Implementations must be thread-safe."""

    def emit(self, event: AuditEvent) -> None:
        ...


class NullSink:
    """Discards all events. Use when audit logging is not needed."""

    def emit(self, event: AuditEvent) -> None:
        return


class StdoutSink:
    """Emits events as single-line JSON to stdout. Useful for local development
    and for piping into log-collection agents.
    """

    def __init__(self, stream: TextIO | None = None) -> None:
        self._stream = stream or sys.stdout

    def emit(self, event: AuditEvent) -> None:
        self._stream.write(event.to_json() + "\n")
        self._stream.flush()


class JsonlFileSink:
    """Appends events to a JSONL file. Opens lazily and flushes after each write.

    For production, prefer a sink that forwards to your SIEM or log aggregator
    rather than writing files directly. This sink is suitable for development
    and for use cases where a local audit log is the archive of record.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event: AuditEvent) -> None:
        with self._path.open("a", encoding="utf-8") as f:
            f.write(event.to_json() + "\n")


class MemorySink:
    """Stores events in memory. Useful for tests."""

    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def emit(self, event: AuditEvent) -> None:
        self.events.append(event)

    def by_kind(self, kind: str) -> list[AuditEvent]:
        return [e for e in self.events if e.kind == kind]

    def clear(self) -> None:
        self.events.clear()


class FanoutSink:
    """Emits each event to multiple sinks. Exceptions in individual sinks
    are caught and logged to stderr rather than propagated, so one broken
    sink does not break the others.
    """

    def __init__(self, *sinks: AuditSink) -> None:
        self._sinks = sinks

    def emit(self, event: AuditEvent) -> None:
        for sink in self._sinks:
            try:
                sink.emit(event)
            except Exception as exc:  # noqa: BLE001 — deliberately broad
                sys.stderr.write(
                    f"[iaiso.audit] sink {type(sink).__name__} failed: {exc}\n"
                )
