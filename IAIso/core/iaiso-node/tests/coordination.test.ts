import { describe, expect, it } from "vitest";

import { MemorySink } from "../src/audit/sinks/memory.js";
import {
  RedisCoordinator,
  SharedPressureCoordinator,
  UPDATE_AND_FETCH_SCRIPT,
  parseHgetallFlat,
} from "../src/coordination/index.js";
import type { RedisClientLike } from "../src/coordination/index.js";
import {
  SumAggregator,
  MaxAggregator,
  WeightedSumAggregator,
} from "../src/policy/index.js";

describe("SharedPressureCoordinator (memory)", () => {
  it("registers executions and aggregates sum by default", () => {
    const sink = new MemorySink();
    const coord = new SharedPressureCoordinator({ audit_sink: sink });
    coord.register("exec-a");
    coord.register("exec-b");
    coord.update("exec-a", 0.3);
    const snap = coord.update("exec-b", 0.5);
    expect(snap.aggregate_pressure).toBeCloseTo(0.8, 9);
    expect(snap.active_executions).toBe(2);
  });

  it("fires onEscalation callback when crossing threshold", () => {
    let escalated = false;
    const coord = new SharedPressureCoordinator({
      escalation_threshold: 0.7,
      release_threshold: 0.95,
      notify_cooldown_seconds: 0,
      callbacks: { onEscalation: () => { escalated = true; } },
    });
    coord.register("a");
    coord.update("a", 0.8);
    expect(escalated).toBe(true);
  });

  it("fires onRelease when crossing release threshold", () => {
    let released = false;
    const coord = new SharedPressureCoordinator({
      escalation_threshold: 0.5,
      release_threshold: 0.9,
      notify_cooldown_seconds: 0,
      callbacks: { onRelease: () => { released = true; } },
    });
    coord.register("a");
    coord.update("a", 0.95);
    expect(released).toBe(true);
  });

  it("supports MaxAggregator", () => {
    const coord = new SharedPressureCoordinator({ aggregator: new MaxAggregator() });
    coord.register("a");
    coord.register("b");
    coord.update("a", 0.3);
    const snap = coord.update("b", 0.7);
    expect(snap.aggregate_pressure).toBeCloseTo(0.7, 9);
  });

  it("supports WeightedSumAggregator", () => {
    const agg = new WeightedSumAggregator({ important: 2.0 }, 1.0);
    const coord = new SharedPressureCoordinator({ aggregator: agg });
    coord.register("important");
    coord.register("normal");
    coord.update("important", 0.5);
    const snap = coord.update("normal", 0.3);
    expect(snap.aggregate_pressure).toBeCloseTo(2.0 * 0.5 + 1.0 * 0.3, 9);
  });

  it("reset() zeros pressures and returns to nominal", () => {
    const coord = new SharedPressureCoordinator({
      escalation_threshold: 0.5,
      release_threshold: 0.9,
      notify_cooldown_seconds: 0,
    });
    coord.register("a");
    coord.update("a", 0.7);
    const count = coord.reset();
    expect(count).toBe(1);
    expect(coord.snapshot().lifecycle).toBe("nominal");
    expect(coord.snapshot().aggregate_pressure).toBe(0);
  });

  it("rejects pressure outside [0, 1]", () => {
    const coord = new SharedPressureCoordinator();
    expect(() => coord.update("a", 1.5)).toThrow(RangeError);
    expect(() => coord.update("a", -0.1)).toThrow(RangeError);
  });

  it("rejects release <= escalation", () => {
    expect(() => new SharedPressureCoordinator({
      escalation_threshold: 5.0,
      release_threshold: 3.0,
    })).toThrow(/release_threshold must exceed/);
  });
});

/** Mock Redis client implementing RedisClientLike, backed by a Map. */
class MockRedis implements RedisClientLike {
  readonly store = new Map<string, Map<string, string>>();

  async eval(
    script: string,
    _numkeys: number,
    ...args: Array<string | number>
  ): Promise<unknown> {
    const key = String(args[0]);
    const hash = this.store.get(key) ?? new Map();
    this.store.set(key, hash);

    // Recognize the IAIso update-and-fetch script by its signature
    if (script.includes("HSET") && script.includes("HGETALL") && args.length >= 4) {
      const execId = String(args[1]);
      const pressure = String(args[2]);
      hash.set(execId, pressure);
      // ignore TTL in mock
      const flat: string[] = [];
      for (const [k, v] of hash) {
        flat.push(k, v);
      }
      return flat;
    }

    // Recognize HDEL helper
    if (script.includes("HDEL")) {
      const execId = String(args[1]);
      hash.delete(execId);
      return 1;
    }

    // Recognize plain HGETALL
    if (script.includes("HGETALL")) {
      const flat: string[] = [];
      for (const [k, v] of hash) {
        flat.push(k, v);
      }
      return flat;
    }

    throw new Error(`unhandled script: ${script.slice(0, 80)}`);
  }

  async hkeys(key: string): Promise<string[]> {
    const h = this.store.get(key);
    return h ? Array.from(h.keys()) : [];
  }

  async hset(
    key: string,
    ...args: Array<string | number>
  ): Promise<number> {
    const hash = this.store.get(key) ?? new Map();
    this.store.set(key, hash);
    let added = 0;
    for (let i = 0; i < args.length; i += 2) {
      const k = String(args[i]);
      const v = String(args[i + 1]);
      if (!hash.has(k)) added++;
      hash.set(k, v);
    }
    return added;
  }
}

describe("RedisCoordinator (with MockRedis)", () => {
  it("register + update + snapshot matches memory semantics", async () => {
    const redis = new MockRedis();
    const coord = new RedisCoordinator({
      redis,
      coordinator_id: "test",
      aggregator: new SumAggregator(),
    });
    await coord.register("exec-a");
    await coord.register("exec-b");
    await coord.update("exec-a", 0.4);
    const snap = await coord.update("exec-b", 0.3);
    expect(snap.aggregate_pressure).toBeCloseTo(0.7, 9);
    expect(snap.active_executions).toBe(2);
  });

  it("uses the normative Lua script verbatim", () => {
    expect(UPDATE_AND_FETCH_SCRIPT).toContain("pressures_key = KEYS[1]");
    expect(UPDATE_AND_FETCH_SCRIPT).toContain("HSET");
    expect(UPDATE_AND_FETCH_SCRIPT).toContain("HGETALL");
    expect(UPDATE_AND_FETCH_SCRIPT).toContain("EXPIRE");
  });

  it("parseHgetallFlat returns a parsed record", () => {
    const parsed = parseHgetallFlat(["a", "0.3", "b", "0.7"]);
    expect(parsed).toEqual({ a: 0.3, b: 0.7 });
  });

  it("reset() zeroes all keys in Redis", async () => {
    const redis = new MockRedis();
    const coord = new RedisCoordinator({ redis });
    await coord.register("a");
    await coord.register("b");
    await coord.update("a", 0.5);
    await coord.update("b", 0.5);
    const count = await coord.reset();
    expect(count).toBe(2);
    const snap = await coord.snapshot();
    expect(snap.aggregate_pressure).toBe(0);
  });

  it("rejects release <= escalation", () => {
    const redis = new MockRedis();
    expect(() => new RedisCoordinator({
      redis,
      escalation_threshold: 8.0,
      release_threshold: 5.0,
    })).toThrow(/release_threshold must exceed/);
  });
});
