"""Tests for audit sinks."""

from __future__ import annotations

import io
import json
from pathlib import Path

from iaiso import (
    AuditEvent,
    FanoutSink,
    JsonlFileSink,
    MemorySink,
    StdoutSink,
)


def _event(kind: str = "test.event") -> AuditEvent:
    return AuditEvent(
        execution_id="t1",
        kind=kind,
        timestamp=1700000000.0,
        data={"k": "v"},
    )


def test_memory_sink_records() -> None:
    sink = MemorySink()
    sink.emit(_event("a"))
    sink.emit(_event("b"))
    sink.emit(_event("a"))
    assert len(sink.events) == 3
    assert len(sink.by_kind("a")) == 2


def test_stdout_sink_writes_json_line() -> None:
    stream = io.StringIO()
    sink = StdoutSink(stream=stream)
    sink.emit(_event())
    stream.seek(0)
    line = stream.read().strip()
    parsed = json.loads(line)
    assert parsed["kind"] == "test.event"
    assert parsed["execution_id"] == "t1"


def test_jsonl_file_sink_appends(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    sink = JsonlFileSink(path)
    sink.emit(_event("one"))
    sink.emit(_event("two"))

    lines = path.read_text().strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["kind"] == "one"
    assert json.loads(lines[1])["kind"] == "two"


def test_fanout_propagates_to_all() -> None:
    a = MemorySink()
    b = MemorySink()
    fan = FanoutSink(a, b)
    fan.emit(_event())
    assert len(a.events) == 1
    assert len(b.events) == 1


def test_fanout_tolerates_broken_sink(capsys) -> None:
    class BrokenSink:
        def emit(self, event: AuditEvent) -> None:
            raise RuntimeError("boom")

    a = MemorySink()
    fan = FanoutSink(BrokenSink(), a)
    fan.emit(_event())
    # The working sink still got the event.
    assert len(a.events) == 1
    captured = capsys.readouterr()
    assert "BrokenSink" in captured.err
