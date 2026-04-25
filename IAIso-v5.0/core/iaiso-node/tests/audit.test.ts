import { describe, expect, it } from "vitest";

import { AuditEvent, SCHEMA_VERSION } from "../src/audit/event.js";
import { FanoutSink, MemorySink, NullSink } from "../src/audit/sinks/memory.js";

describe("AuditEvent", () => {
  it("serializes to spec-compliant JSON envelope", () => {
    const ev = new AuditEvent("exec-1", "engine.step", 1700000000.5, { step: 1 });
    const j = ev.toJSON();
    expect(j.schema_version).toBe(SCHEMA_VERSION);
    expect(j.execution_id).toBe("exec-1");
    expect(j.kind).toBe("engine.step");
    expect(j.timestamp).toBe(1700000000.5);
    expect(j.data).toEqual({ step: 1 });
  });

  it("round-trips through JSON string", () => {
    const ev = new AuditEvent("exec-1", "a.b", 1, { x: [1, 2, 3] });
    const parsed = JSON.parse(ev.toJsonString());
    expect(parsed.schema_version).toBe(SCHEMA_VERSION);
    expect(parsed.data.x).toEqual([1, 2, 3]);
  });
});

describe("MemorySink", () => {
  it("records emitted events", () => {
    const sink = new MemorySink();
    const ev = new AuditEvent("exec-1", "test", 0, {});
    sink.emit(ev);
    expect(sink.events).toHaveLength(1);
    expect(sink.events[0]).toBe(ev);
  });

  it("clears events", () => {
    const sink = new MemorySink();
    sink.emit(new AuditEvent("x", "y", 0, {}));
    sink.clear();
    expect(sink.events).toHaveLength(0);
  });
});

describe("NullSink", () => {
  it("silently accepts events", () => {
    const sink = new NullSink();
    expect(() => sink.emit(new AuditEvent("x", "y", 0, {}))).not.toThrow();
  });
});

describe("FanoutSink", () => {
  it("emits to every child sink", async () => {
    const a = new MemorySink();
    const b = new MemorySink();
    const fanout = new FanoutSink([a, b]);
    await fanout.emit(new AuditEvent("x", "y", 0, {}));
    expect(a.events).toHaveLength(1);
    expect(b.events).toHaveLength(1);
  });
});
