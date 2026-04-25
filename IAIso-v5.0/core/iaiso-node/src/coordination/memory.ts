/**
 * In-memory cross-execution pressure coordinator.
 *
 * Port of `iaiso.coordination.SharedPressureCoordinator` from the Python
 * reference. Tracks per-execution pressure and an aggregate; emits
 * fleet-level audit events when the aggregate crosses thresholds.
 *
 * For multi-process fleets, use `RedisCoordinator` from
 * `@iaiso/core/coordination/redis`.
 */

import { AuditEvent } from "../audit/event.js";
import type { AuditSink } from "../audit/sinks/memory.js";
import { NullSink } from "../audit/sinks/memory.js";
import type { Aggregator } from "../policy/index.js";
import { SumAggregator } from "../policy/index.js";

export type CoordinatorLifecycle = "nominal" | "escalated" | "released";

export interface CoordinatorCallbacks {
  onEscalation?: (snapshot: CoordinatorSnapshot) => void;
  onRelease?: (snapshot: CoordinatorSnapshot) => void;
}

export interface CoordinatorSnapshot {
  coordinator_id: string;
  aggregate_pressure: number;
  lifecycle: CoordinatorLifecycle;
  active_executions: number;
  per_execution: Record<string, number>;
}

export interface SharedPressureCoordinatorOptions {
  coordinator_id?: string;
  escalation_threshold?: number;
  release_threshold?: number;
  aggregator?: Aggregator;
  audit_sink?: AuditSink;
  callbacks?: CoordinatorCallbacks;
  notify_cooldown_seconds?: number;
  /** Clock for cooldown timing. Defaults to Date.now()/1000. */
  clock?: () => number;
}

export class SharedPressureCoordinator {
  readonly coordinator_id: string;
  readonly escalation_threshold: number;
  readonly release_threshold: number;
  readonly aggregator: Aggregator;
  readonly audit_sink: AuditSink;
  readonly callbacks: CoordinatorCallbacks;
  readonly notify_cooldown_seconds: number;
  private readonly _clock: () => number;

  protected _pressures = new Map<string, number>();
  protected _lifecycle: CoordinatorLifecycle = "nominal";
  protected _lastNotifyAt = 0.0;

  constructor(opts: SharedPressureCoordinatorOptions = {}) {
    this.coordinator_id = opts.coordinator_id ?? "default";
    this.escalation_threshold = opts.escalation_threshold ?? 5.0;
    this.release_threshold = opts.release_threshold ?? 8.0;
    this.aggregator = opts.aggregator ?? new SumAggregator();
    this.audit_sink = opts.audit_sink ?? new NullSink();
    this.callbacks = opts.callbacks ?? {};
    this.notify_cooldown_seconds = opts.notify_cooldown_seconds ?? 1.0;
    this._clock = opts.clock ?? (() => Date.now() / 1000);

    if (this.release_threshold <= this.escalation_threshold) {
      throw new RangeError(
        "release_threshold must exceed escalation_threshold",
      );
    }

    this._emit("coordinator.init", {
      coordinator_id: this.coordinator_id,
      aggregator: this.aggregator.name,
      backend: "memory",
    });
  }

  register(execution_id: string): CoordinatorSnapshot {
    this._pressures.set(execution_id, 0.0);
    this._emit("coordinator.execution_registered", { execution_id });
    return this.snapshot();
  }

  unregister(execution_id: string): CoordinatorSnapshot {
    this._pressures.delete(execution_id);
    this._emit("coordinator.execution_unregistered", { execution_id });
    return this.snapshot();
  }

  update(execution_id: string, pressure: number): CoordinatorSnapshot {
    if (pressure < 0 || pressure > 1) {
      throw new RangeError("pressure must be in [0, 1]");
    }
    this._pressures.set(execution_id, pressure);
    return this._evaluate();
  }

  reset(): number {
    const fleet_size = this._pressures.size;
    for (const k of this._pressures.keys()) this._pressures.set(k, 0.0);
    this._lifecycle = "nominal";
    this._emit("coordinator.reset", { fleet_size });
    return fleet_size;
  }

  snapshot(): CoordinatorSnapshot {
    return {
      coordinator_id: this.coordinator_id,
      aggregate_pressure: this.aggregator.aggregate(this._pressures),
      lifecycle: this._lifecycle,
      active_executions: this._pressures.size,
      per_execution: Object.fromEntries(this._pressures),
    };
  }

  protected _evaluate(): CoordinatorSnapshot {
    const aggregate = this.aggregator.aggregate(this._pressures);
    const now = this._clock();
    const inCooldown = now - this._lastNotifyAt < this.notify_cooldown_seconds;

    if (aggregate >= this.release_threshold) {
      if (this._lifecycle !== "released") {
        this._lifecycle = "released";
        if (!inCooldown) {
          this._emit("coordinator.release", {
            aggregate_pressure: aggregate,
            threshold: this.release_threshold,
          });
          this._lastNotifyAt = now;
          this._safeCallback("onRelease");
        }
      }
    } else if (aggregate >= this.escalation_threshold) {
      if (this._lifecycle === "nominal") {
        this._lifecycle = "escalated";
        if (!inCooldown) {
          this._emit("coordinator.escalation", {
            aggregate_pressure: aggregate,
            threshold: this.escalation_threshold,
          });
          this._lastNotifyAt = now;
          this._safeCallback("onEscalation");
        }
      }
    } else {
      if (this._lifecycle !== "nominal") {
        this._lifecycle = "nominal";
        if (!inCooldown) {
          this._emit("coordinator.returned_to_nominal", {
            aggregate_pressure: aggregate,
          });
          this._lastNotifyAt = now;
        }
      }
    }
    return this.snapshot();
  }

  private _safeCallback(which: "onEscalation" | "onRelease"): void {
    const cb = this.callbacks[which];
    if (!cb) return;
    try {
      cb(this.snapshot());
    } catch (exc) {
      this._emit("coordinator.callback_error", {
        callback: which === "onEscalation" ? "on_escalation" : "on_release",
        error: (exc as Error).message,
      });
    }
  }

  protected _emit(kind: string, data: Record<string, unknown>): void {
    this.audit_sink.emit(
      new AuditEvent(
        `coord:${this.coordinator_id}`,
        kind,
        this._clock(),
        data,
      ),
    );
  }
}
