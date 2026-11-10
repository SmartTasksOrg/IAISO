/**
 * Regression tests for the `enforcement_mode` boot guard (WI-4) and the
 * cost-governance surface (WI-5).
 */

import { beforeEach, describe, expect, it } from "vitest";

import { MemorySink, NullSink } from "../audit/sinks/memory.js";
import {
  ENFORCEMENT_PERMISSIVE,
  ENFORCEMENT_STRICT,
  PressureConfig,
  PressureEngine,
  StepInput,
  StrictModeError,
  _resetWarnings,
  setWarnLogger,
} from "./engine.js";
import { Lifecycle, StepOutcome } from "./types.js";

/** A config that has been moved off library defaults. */
function calibrated(overrides: Record<string, unknown> = {}): PressureConfig {
  return new PressureConfig({ token_coefficient: 0.011, ...overrides });
}

function scripted(values: number[]): () => number {
  let i = 0;
  let last = 0;
  return () => {
    if (i < values.length) last = values[i++]!;
    return last;
  };
}

beforeEach(() => {
  _resetWarnings();
  setWarnLogger(() => {});
});

// ---------------------------------------------------------------------------
// WI-4 — boot guard
// ---------------------------------------------------------------------------

describe("enforcement_mode boot guard", () => {
  it("strict refuses a NullSink", () => {
    expect(() =>
      new PressureEngine(calibrated(), {
        execution_id: "t",
        audit_sink: new NullSink(),
        enforcement_mode: ENFORCEMENT_STRICT,
      }),
    ).toThrow(/NullSink/);
  });

  it("strict refuses an omitted sink", () => {
    // Omitting the sink is the same degraded condition as passing NullSink;
    // it must not be a way around the guard.
    expect(() =>
      new PressureEngine(calibrated(), {
        execution_id: "t",
        enforcement_mode: ENFORCEMENT_STRICT,
      }),
    ).toThrow(StrictModeError);
  });

  it("strict refuses post_release_lock=false", () => {
    expect(() =>
      new PressureEngine(calibrated({ post_release_lock: false }), {
        execution_id: "t",
        audit_sink: new MemorySink(),
        enforcement_mode: ENFORCEMENT_STRICT,
      }),
    ).toThrow(/post_release_lock/);
  });

  it("strict refuses uncalibrated defaults", () => {
    expect(() =>
      new PressureEngine(new PressureConfig(), {
        execution_id: "t",
        audit_sink: new MemorySink(),
        enforcement_mode: ENFORCEMENT_STRICT,
      }),
    ).toThrow(/calibrat/);
  });

  it("strict accepts defaults when a calibration artifact is named", () => {
    const engine = new PressureEngine(new PressureConfig(), {
      execution_id: "t",
      audit_sink: new MemorySink(),
      enforcement_mode: ENFORCEMENT_STRICT,
      calibration_artifact: "calibration/2026-07-01.json",
    });
    expect(engine.enforcement_mode).toBe(ENFORCEMENT_STRICT);
  });

  it("strict refuses an auto-generated HS256 consent key", () => {
    expect(() =>
      new PressureEngine(calibrated(), {
        execution_id: "t",
        audit_sink: new MemorySink(),
        enforcement_mode: ENFORCEMENT_STRICT,
        consent_algorithm: "HS256",
        consent_key_auto_generated: true,
      }),
    ).toThrow(/HS256/);
  });

  it("strict accepts a sound config", () => {
    const engine = new PressureEngine(calibrated(), {
      execution_id: "t",
      audit_sink: new MemorySink(),
      enforcement_mode: ENFORCEMENT_STRICT,
    });
    expect(engine.enforcement_mode).toBe(ENFORCEMENT_STRICT);
  });

  it("permissive is the default and proceeds", () => {
    const engine = new PressureEngine(new PressureConfig(), {
      execution_id: "t",
    });
    expect(engine.enforcement_mode).toBe(ENFORCEMENT_PERMISSIVE);
  });

  it("permissive warns once per condition per process", () => {
    const seen: string[] = [];
    setWarnLogger((m) => seen.push(m));
    new PressureEngine(new PressureConfig(), {
      execution_id: "a",
      audit_sink: new NullSink(),
    });
    new PressureEngine(new PressureConfig(), {
      execution_id: "b",
      audit_sink: new NullSink(),
    });
    expect(seen.filter((m) => m.includes("NullSink")).length).toBe(1);
  });

  it("rejects an unknown enforcement mode", () => {
    expect(
      () =>
        new PressureEngine(calibrated(), {
          execution_id: "t",
          audit_sink: new MemorySink(),
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          enforcement_mode: "advisory" as any,
        }),
    ).toThrow(/enforcement_mode/);
  });

  it("a strict refusal leaves nothing constructed", () => {
    // An engine that emitted engine.init before refusing would be a lie in
    // the audit log.
    const sink = new MemorySink();
    expect(
      () =>
        new PressureEngine(new PressureConfig({ post_release_lock: false }), {
          execution_id: "t",
          audit_sink: sink,
          enforcement_mode: ENFORCEMENT_STRICT,
        }),
    ).toThrow(StrictModeError);
    expect(sink.events.length).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// WI-5 — cost governance
// ---------------------------------------------------------------------------

function costConfig(overrides: Record<string, unknown> = {}): PressureConfig {
  return new PressureConfig({
    dissipation_per_step: 0.0,
    model_costs: { frontier: 15.0, small: 0.5 },
    ...overrides,
  });
}

describe("cost governance", () => {
  it("tracks spend and emits spend_usd", () => {
    const sink = new MemorySink();
    const engine = new PressureEngine(costConfig(), {
      execution_id: "t",
      audit_sink: sink,
      clock: scripted([0, 1, 2]),
    });
    engine.step(new StepInput({ tokens: 100_000, model: "frontier" }));

    expect(engine.spend_usd).toBeCloseTo(1.5, 9);
    const steps = sink.events.filter((e) => e.kind === "engine.step");
    expect(steps[0]!.data["spend_usd"]).toBeCloseTo(1.5, 9);
  });

  it("omits spend_usd when no model_costs are configured", () => {
    // Existing consumers of the frozen 1.0 envelope must not see a new key.
    const sink = new MemorySink();
    const engine = new PressureEngine(
      new PressureConfig({ dissipation_per_step: 0.0 }),
      { execution_id: "t", audit_sink: sink, clock: scripted([0, 1]) },
    );
    engine.step(new StepInput({ tokens: 1000 }));
    const steps = sink.events.filter((e) => e.kind === "engine.step");
    expect("spend_usd" in steps[0]!.data).toBe(false);
  });

  it("charges nothing for an unpriced model", () => {
    const engine = new PressureEngine(costConfig(), {
      execution_id: "t",
      audit_sink: new MemorySink(),
      clock: scripted([0, 1]),
    });
    engine.step(new StepInput({ tokens: 1_000_000, model: "unpriced" }));
    expect(engine.spend_usd).toBe(0);
  });

  it("budget exhaustion reuses the lock path", () => {
    const sink = new MemorySink();
    const engine = new PressureEngine(costConfig({ budget_usd: 1.0 }), {
      execution_id: "t",
      audit_sink: sink,
      clock: scripted([0, 1, 2]),
    });
    const outcome = engine.step(
      new StepInput({ tokens: 100_000, model: "frontier" }),
    );

    expect(outcome).toBe(StepOutcome.Locked);
    expect(engine.lifecycle).toBe(Lifecycle.Locked);

    const locked = sink.events.filter((e) => e.kind === "engine.locked");
    expect(locked[0]!.data["reason"]).toBe("budget_exceeded");

    // No new lifecycle state was invented.
    const kinds = new Set(sink.events.map((e) => e.kind));
    for (const k of kinds) {
      expect([
        "engine.init",
        "engine.step",
        "engine.locked",
        "engine.release",
        "engine.reset",
        "engine.escalation",
        "engine.step.rejected",
      ]).toContain(k);
    }
  });

  it("a budget-locked engine rejects further steps", () => {
    const engine = new PressureEngine(costConfig({ budget_usd: 1.0 }), {
      execution_id: "t",
      audit_sink: new MemorySink(),
      clock: scripted([0, 1, 2, 3]),
    });
    engine.step(new StepInput({ tokens: 100_000, model: "frontier" }));
    expect(engine.step(new StepInput({ tokens: 1 }))).toBe(StepOutcome.Locked);
  });

  it("reset clears spend", () => {
    const engine = new PressureEngine(costConfig(), {
      execution_id: "t",
      audit_sink: new MemorySink(),
      clock: scripted([0, 1, 2]),
    });
    engine.step(new StepInput({ tokens: 100_000, model: "frontier" }));
    expect(engine.spend_usd).toBeGreaterThan(0);
    engine.reset();
    expect(engine.spend_usd).toBe(0);
  });

  it("rejects a negative budget", () => {
    expect(() => new PressureConfig({ budget_usd: -1 })).toThrow(/budget_usd/);
  });

  it("rejects a negative model cost", () => {
    expect(() => new PressureConfig({ model_costs: { frontier: -1 } })).toThrow(
      /model_costs/,
    );
  });
});
