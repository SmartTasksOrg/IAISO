/**
 * Redis-backed cross-execution coordinator.
 *
 * Implements the wire contract specified in `spec/coordinator/README.md §1`:
 * the Redis keyspace, the atomic Lua update-and-fetch script, the hash
 * key layout, and the reset semantics. Interoperable with the Python
 * reference's `RedisCoordinator` — processes on both runtimes connecting
 * to the same Redis instance with the same `(key_prefix, coordinator_id)`
 * tuple share state.
 *
 * Install:
 *   npm install ioredis
 *
 * Example:
 *   import Redis from "ioredis";
 *   import {
 *     RedisCoordinator,
 *     SumAggregator,
 *   } from "@iaiso/core/coordination/redis";
 *
 *   const redis = new Redis(process.env.REDIS_URL);
 *   const coord = new RedisCoordinator({
 *     redis,
 *     coordinator_id: "prod-fleet",
 *     escalation_threshold: 5.0,
 *     release_threshold: 8.0,
 *   });
 *   await coord.update("exec-abc", 0.42);
 *   const snap = await coord.snapshot();
 */

import { SharedPressureCoordinator } from "./memory.js";
import type {
  CoordinatorSnapshot,
  SharedPressureCoordinatorOptions,
} from "./memory.js";
import type { AuditSink } from "../audit/sinks/memory.js";

/**
 * The normative Lua script from `spec/coordinator/README.md §1.2`.
 * Verbatim — do not edit without updating the spec and vectors.
 */
export const UPDATE_AND_FETCH_SCRIPT = `
local pressures_key = KEYS[1]
local exec_id       = ARGV[1]
local new_pressure  = ARGV[2]
local ttl_seconds   = tonumber(ARGV[3])

redis.call('HSET', pressures_key, exec_id, new_pressure)
if ttl_seconds > 0 then
  redis.call('EXPIRE', pressures_key, ttl_seconds)
end

return redis.call('HGETALL', pressures_key)
`.trim();

/**
 * Structural type for the subset of ioredis/node-redis API we use.
 * Using a structural type so we don't take `ioredis` as a hard import.
 */
export interface RedisClientLike {
  eval(
    script: string,
    numkeys: number,
    ...args: Array<string | number>
  ): Promise<unknown>;
  hkeys(key: string): Promise<string[]>;
  hset(
    key: string,
    ...args: Array<string | number>
  ): Promise<number | string>;
}

export interface RedisCoordinatorOptions
  extends SharedPressureCoordinatorOptions {
  redis: RedisClientLike;
  /** Keyspace prefix. Wrap in hash tags for Redis Cluster. Default: "iaiso:coord". */
  key_prefix?: string;
  /** TTL refresh on the pressures hash. Default: 300 seconds. 0 to disable. */
  pressures_ttl_seconds?: number;
}

/**
 * Redis-backed coordinator. All cross-process state lives in Redis;
 * this class is otherwise a thin wrapper.
 *
 * `update()`, `snapshot()`, `reset()`, `register()`, and `unregister()`
 * are all async because they make Redis round trips.
 */
export class RedisCoordinator {
  readonly coordinator_id: string;
  readonly escalation_threshold: number;
  readonly release_threshold: number;
  readonly key_prefix: string;
  readonly pressures_ttl_seconds: number;
  private readonly _redis: RedisClientLike;
  private readonly _inMemShadow: ShadowCoordinator;

  constructor(opts: RedisCoordinatorOptions) {
    this._redis = opts.redis;
    this.coordinator_id = opts.coordinator_id ?? "default";
    this.escalation_threshold = opts.escalation_threshold ?? 5.0;
    this.release_threshold = opts.release_threshold ?? 8.0;
    this.key_prefix = opts.key_prefix ?? "iaiso:coord";
    this.pressures_ttl_seconds = opts.pressures_ttl_seconds ?? 300.0;

    if (this.release_threshold <= this.escalation_threshold) {
      throw new RangeError(
        "release_threshold must exceed escalation_threshold",
      );
    }

    // Piggyback the in-memory coordinator for threshold-transition
    // accounting and event emission. We feed it post-Lua snapshots so
    // its lifecycle/evaluate logic works uniformly.
    this._inMemShadow = new ShadowCoordinator({
      coordinator_id: this.coordinator_id,
      escalation_threshold: this.escalation_threshold,
      release_threshold: this.release_threshold,
      aggregator: opts.aggregator,
      audit_sink: opts.audit_sink,
      callbacks: opts.callbacks,
      notify_cooldown_seconds: opts.notify_cooldown_seconds,
      clock: opts.clock,
      backend_label: "redis",
    });
  }

  private _pressuresKey(): string {
    return `${this.key_prefix}:${this.coordinator_id}:pressures`;
  }

  async register(execution_id: string): Promise<CoordinatorSnapshot> {
    await this._redis.hset(this._pressuresKey(), execution_id, "0.0");
    this._inMemShadow.setExecution(execution_id, 0.0);
    this._inMemShadow.emitPublic("coordinator.execution_registered", {
      execution_id,
    });
    return this._inMemShadow.snapshot();
  }

  async unregister(execution_id: string): Promise<CoordinatorSnapshot> {
    // hdel via eval (ioredis supports `hdel` too, but avoid widening our
    // structural type for it — use eval for a minimal surface).
    await this._redis.eval(
      `redis.call('HDEL', KEYS[1], ARGV[1]); return 1`,
      1,
      this._pressuresKey(),
      execution_id,
    );
    this._inMemShadow.deleteExecution(execution_id);
    this._inMemShadow.emitPublic("coordinator.execution_unregistered", {
      execution_id,
    });
    return this._inMemShadow.snapshot();
  }

  async update(
    execution_id: string,
    pressure: number,
  ): Promise<CoordinatorSnapshot> {
    if (pressure < 0 || pressure > 1) {
      throw new RangeError("pressure must be in [0, 1]");
    }

    const flat = (await this._redis.eval(
      UPDATE_AND_FETCH_SCRIPT,
      1,
      this._pressuresKey(),
      execution_id,
      String(pressure),
      String(Math.floor(this.pressures_ttl_seconds)),
    )) as string[];

    const parsed = parseHgetallFlat(flat);
    this._inMemShadow.replacePressures(parsed);
    return this._inMemShadow.evaluatePublic();
  }

  async snapshot(): Promise<CoordinatorSnapshot> {
    // Refresh from Redis, then return shadow snapshot.
    const flat = (await this._redis.eval(
      `return redis.call('HGETALL', KEYS[1])`,
      1,
      this._pressuresKey(),
    )) as string[];
    this._inMemShadow.replacePressures(parseHgetallFlat(flat));
    return this._inMemShadow.snapshot();
  }

  async reset(): Promise<number> {
    const keys = await this._redis.hkeys(this._pressuresKey());
    if (keys.length === 0) {
      this._inMemShadow.resetAllToZero();
      this._inMemShadow.emitPublic("coordinator.reset", { fleet_size: 0 });
      return 0;
    }
    const args: string[] = [];
    for (const k of keys) {
      args.push(k, "0.0");
    }
    await this._redis.hset(this._pressuresKey(), ...args);
    this._inMemShadow.resetAllToZero();
    this._inMemShadow.emitPublic("coordinator.reset", {
      fleet_size: keys.length,
    });
    return keys.length;
  }
}

/** Parse a Redis HGETALL flat array into an object. */
export function parseHgetallFlat(flat: unknown[]): Record<string, number> {
  const out: Record<string, number> = {};
  for (let i = 0; i < flat.length; i += 2) {
    const key = String(flat[i]);
    const val = Number(flat[i + 1]);
    out[key] = val;
  }
  return out;
}

/**
 * Internal: extends SharedPressureCoordinator to expose the mutators
 * the Redis wrapper needs and override the backend label on init event.
 */
class ShadowCoordinator extends SharedPressureCoordinator {
  constructor(
    opts: SharedPressureCoordinatorOptions & { backend_label?: string },
  ) {
    super({
      ...opts,
      // suppress the default "memory" init event from the base class;
      // we emit our own below with the correct backend label.
      audit_sink: { emit: () => {} },
    });
    // Restore the real audit sink
    (this as unknown as { audit_sink: AuditSink }).audit_sink =
      opts.audit_sink ?? { emit: () => {} };
    // Emit init with the correct backend
    this.emitPublic("coordinator.init", {
      coordinator_id: this.coordinator_id,
      aggregator: this.aggregator.name,
      backend: opts.backend_label ?? "memory",
    });
  }

  setExecution(id: string, pressure: number): void {
    this._pressures.set(id, pressure);
  }

  deleteExecution(id: string): void {
    this._pressures.delete(id);
  }

  replacePressures(values: Record<string, number>): void {
    this._pressures = new Map(Object.entries(values));
  }

  resetAllToZero(): void {
    for (const k of this._pressures.keys()) this._pressures.set(k, 0.0);
    this._lifecycle = "nominal";
  }

  evaluatePublic(): CoordinatorSnapshot {
    return this._evaluate();
  }

  emitPublic(kind: string, data: Record<string, unknown>): void {
    this._emit(kind, data);
  }
}
