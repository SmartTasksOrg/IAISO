import { describe, expect, it } from "vitest";

import { AuditEvent } from "../src/audit/event.js";
import { PrometheusMetricsSink } from "../src/metrics/prometheus.js";
import { OtelSpanSink } from "../src/observability/tracing.js";

// Mock prom-client: track all counter/gauge/histogram observations
class FakeMetric {
  calls: Array<{ method: string; args: unknown[] }> = [];
  inc(...args: unknown[]) {
    this.calls.push({ method: "inc", args });
  }
  set(...args: unknown[]) {
    this.calls.push({ method: "set", args });
  }
  observe(...args: unknown[]) {
    this.calls.push({ method: "observe", args });
  }
}

const makeFakePromClient = () => {
  const built: Record<string, FakeMetric> = {};
  const factory = (cls: string) =>
    class {
      constructor(public opts: { name: string }) {
        built[opts.name] = this as unknown as FakeMetric;
        return new FakeMetric() as unknown as {
          opts: { name: string };
        };
      }
    };
  return { promClient: {
    Counter: factory("Counter"),
    Gauge: factory("Gauge"),
    Histogram: factory("Histogram"),
  } as any, built };
};

describe("PrometheusMetricsSink", () => {
  it("registers the expected metrics on construction", () => {
    const names: string[] = [];
    class Metric {
      constructor(public opts: { name: string }) {
        names.push(opts.name);
      }
      inc() {}
      set() {}
      observe() {}
    }
    const promClient = {
      Counter: Metric as unknown as typeof Metric,
      Gauge: Metric as unknown as typeof Metric,
      Histogram: Metric as unknown as typeof Metric,
    };
    new PrometheusMetricsSink({ promClient: promClient as any });
    expect(names).toContain("iaiso_events_total");
    expect(names).toContain("iaiso_escalations_total");
    expect(names).toContain("iaiso_releases_total");
    expect(names).toContain("iaiso_pressure");
    expect(names).toContain("iaiso_step_delta");
  });

  it("increments counters on relevant events", () => {
    const inc = { eventsTotal: 0, escalations: 0, releases: 0 };
    const pressureSets: number[] = [];
    const deltaObs: number[] = [];

    class Counter {
      constructor(public opts: { name: string }) {}
      inc() {
        if (this.opts.name === "iaiso_events_total") inc.eventsTotal++;
        if (this.opts.name === "iaiso_escalations_total") inc.escalations++;
        if (this.opts.name === "iaiso_releases_total") inc.releases++;
      }
    }
    class Gauge {
      constructor(public opts: { name: string }) {}
      set(_l: unknown, v?: number) { if (typeof v === "number") pressureSets.push(v); }
    }
    class Histogram {
      constructor(public opts: { name: string }) {}
      observe(v: number) { deltaObs.push(v); }
    }
    const sink = new PrometheusMetricsSink({
      promClient: { Counter, Gauge, Histogram } as any,
    });
    sink.emit(new AuditEvent("e1", "engine.init", 0, {}));
    sink.emit(new AuditEvent("e1", "engine.step", 1, { pressure: 0.3, delta: 0.05 }));
    sink.emit(new AuditEvent("e1", "engine.escalation", 2, { pressure: 0.9 }));
    sink.emit(new AuditEvent("e1", "engine.step", 3, { pressure: 0.96, delta: 0.1 }));
    sink.emit(new AuditEvent("e1", "engine.release", 4, { pressure: 0.96 }));

    expect(inc.eventsTotal).toBe(5);
    expect(inc.escalations).toBe(1);
    expect(inc.releases).toBe(1);
    expect(pressureSets).toEqual([0.3, 0.96]);
    expect(deltaObs).toEqual([0.05, 0.1]);
  });
});

describe("OtelSpanSink", () => {
  it("opens a span on engine.init and closes on execution.closed", () => {
    const spans: Array<{
      name: string;
      events: Array<{ name: string; attrs?: Record<string, unknown> }>;
      attrs: Record<string, unknown>;
      ended: boolean;
    }> = [];

    const tracer = {
      startSpan: (name: string, options?: { attributes?: Record<string, unknown> }) => {
        const span = {
          name,
          events: [] as Array<{ name: string; attrs?: Record<string, unknown> }>,
          attrs: { ...(options?.attributes ?? {}) } as Record<string, unknown>,
          ended: false,
          addEvent(evName: string, attrs?: Record<string, unknown>) {
            this.events.push({ name: evName, attrs });
          },
          setAttribute(k: string, v: unknown) {
            this.attrs[k] = v;
          },
          end() {
            this.ended = true;
          },
        };
        spans.push(span);
        return span;
      },
    };

    const sink = new OtelSpanSink({ tracer: tracer as any });
    sink.emit(new AuditEvent("e1", "engine.init", 0, {}));
    sink.emit(new AuditEvent("e1", "engine.step", 1, { pressure: 0.5, delta: 0.1 }));
    sink.emit(new AuditEvent("e1", "engine.escalation", 2, { pressure: 0.85 }));
    sink.emit(new AuditEvent("e1", "execution.closed", 3, {}));

    expect(spans).toHaveLength(1);
    const [span] = spans;
    expect(span!.name).toBe("iaiso.execution:e1");
    expect(span!.events.map((e) => e.name)).toEqual([
      "engine.init",
      "engine.step",
      "engine.escalation",
      "execution.closed",
    ]);
    expect(span!.attrs["iaiso.pressure"]).toBe(0.5);
    expect(span!.attrs["iaiso.escalated"]).toBe(true);
    expect(span!.ended).toBe(true);
  });

  it("drops events with no open span", () => {
    const startSpan = () => { throw new Error("should not be called"); };
    const sink = new OtelSpanSink({ tracer: { startSpan: startSpan as any } });
    // engine.step before engine.init — should drop quietly, not throw
    expect(() =>
      sink.emit(new AuditEvent("orphan", "engine.step", 0, {}))
    ).not.toThrow();
  });
});
