/**
 * Prometheus metrics sink.
 *
 * Wraps `prom-client` to expose IAIso activity as standard metrics:
 *
 *   iaiso_events_total{kind, execution_id}     # counter
 *   iaiso_pressure                              # gauge (last observed)
 *   iaiso_step_delta                            # histogram
 *   iaiso_escalations_total                     # counter
 *   iaiso_releases_total                        # counter
 *
 * Install:
 *   npm install prom-client
 *
 * Usage:
 *   import { register } from "prom-client";
 *   import { PrometheusMetricsSink } from "@iaiso/core/metrics/prometheus";
 *
 *   const metrics = new PrometheusMetricsSink({ registry: register });
 *   const execSink = new FanoutSink([stdout, metrics]);
 *   // ...later, expose /metrics:
 *   app.get("/metrics", async (req, res) => {
 *     res.set("Content-Type", register.contentType);
 *     res.end(await register.metrics());
 *   });
 */

import type { AuditSink } from "../audit/sinks/memory.js";
import type { AuditEvent } from "../audit/event.js";

// Structural types so we don't hard-import prom-client
interface CounterLike {
  inc(labels?: Record<string, string>, value?: number): void;
}
interface GaugeLike {
  set(labels: Record<string, string>, value: number): void;
  set(value: number): void;
}
interface HistogramLike {
  observe(labels: Record<string, string>, value: number): void;
  observe(value: number): void;
}
interface RegistryLike {
  registerMetric(metric: unknown): void;
}

interface PromClientLike {
  Counter: new (opts: {
    name: string;
    help: string;
    labelNames?: string[];
    registers?: RegistryLike[];
  }) => CounterLike;
  Gauge: new (opts: {
    name: string;
    help: string;
    labelNames?: string[];
    registers?: RegistryLike[];
  }) => GaugeLike;
  Histogram: new (opts: {
    name: string;
    help: string;
    labelNames?: string[];
    buckets?: number[];
    registers?: RegistryLike[];
  }) => HistogramLike;
}

export interface PrometheusMetricsSinkOptions {
  /** The `prom-client` module (pass the module, not individual classes). */
  promClient: PromClientLike;
  /** Optional custom registry; defaults to the module's global registry. */
  registry?: RegistryLike;
  /** Prefix for metric names. Default: `iaiso_`. */
  prefix?: string;
}

export class PrometheusMetricsSink implements AuditSink {
  readonly eventsCounter: CounterLike;
  readonly escalationsCounter: CounterLike;
  readonly releasesCounter: CounterLike;
  readonly pressureGauge: GaugeLike;
  readonly stepDeltaHistogram: HistogramLike;

  constructor(opts: PrometheusMetricsSinkOptions) {
    const p = opts.prefix ?? "iaiso_";
    const registers = opts.registry ? [opts.registry] : undefined;
    const { Counter, Gauge, Histogram } = opts.promClient;

    this.eventsCounter = new Counter({
      name: `${p}events_total`,
      help: "Total IAIso audit events by kind.",
      labelNames: ["kind"],
      registers,
    });
    this.escalationsCounter = new Counter({
      name: `${p}escalations_total`,
      help: "Total engine escalation events.",
      registers,
    });
    this.releasesCounter = new Counter({
      name: `${p}releases_total`,
      help: "Total engine release events.",
      registers,
    });
    this.pressureGauge = new Gauge({
      name: `${p}pressure`,
      help: "Current pressure for the last-observed execution.",
      labelNames: ["execution_id"],
      registers,
    });
    this.stepDeltaHistogram = new Histogram({
      name: `${p}step_delta`,
      help: "Per-step pressure delta before clamping.",
      buckets: [0.0, 0.01, 0.03, 0.05, 0.1, 0.2, 0.5, 1.0],
      registers,
    });
  }

  emit(event: AuditEvent): void {
    this.eventsCounter.inc({ kind: event.kind });
    switch (event.kind) {
      case "engine.escalation":
        this.escalationsCounter.inc();
        break;
      case "engine.release":
        this.releasesCounter.inc();
        break;
      case "engine.step": {
        const p = event.data["pressure"];
        if (typeof p === "number") {
          this.pressureGauge.set({ execution_id: event.executionId }, p);
        }
        const delta = event.data["delta"];
        if (typeof delta === "number") {
          this.stepDeltaHistogram.observe(delta);
        }
        break;
      }
      default:
        break;
    }
  }
}
