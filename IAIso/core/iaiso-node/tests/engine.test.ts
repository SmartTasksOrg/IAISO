import { describe, expect, it } from "vitest";

import { MemorySink } from "../src/audit/sinks/memory.js";
import { PressureConfig, PressureEngine, StepInput } from "../src/core/engine.js";
import { Lifecycle, StepOutcome } from "../src/core/types.js";
import { makeScriptedClock } from "../src/conformance/pressure.js";

describe("PressureConfig", () => {
  it("accepts defaults", () => {
    const cfg = new PressureConfig();
    expect(cfg.escalation_threshold).toBe(0.85);
    expect(cfg.release_threshold).toBe(0.95);
    expect(cfg.post_release_lock).toBe(true);
  });

  it("rejects release <= escalation", () => {
    expect(() => new PressureConfig({ escalation_threshold: 0.9, release_threshold: 0.5 }))
      .toThrow(/release_threshold must exceed escalation_threshold/);
  });

  it("rejects thresholds outside [0, 1]", () => {
    expect(() => new PressureConfig({ escalation_threshold: 1.5 }))
      .toThrow(/escalation_threshold/);
    expect(() => new PressureConfig({ release_threshold: -0.1 }))
      .toThrow(/release_threshold/);
  });

  it("rejects negative coefficients", () => {
    expect(() => new PressureConfig({ token_coefficient: -0.01 }))
      .toThrow(/token_coefficient/);
  });
});

describe("PressureEngine", () => {
  it("emits engine.init on construction", () => {
    const sink = new MemorySink();
    const engine = new PressureEngine(new PressureConfig(), {
      execution_id: "exec-1",
      audit_sink: sink,
      clock: makeScriptedClock([0.0]),
    });
    expect(sink.events).toHaveLength(1);
    expect(sink.events[0]!.kind).toBe("engine.init");
    expect(engine.lifecycle).toBe(Lifecycle.Init);
  });

  it("accumulates tool-call pressure at 0.06 per step", () => {
    const sink = new MemorySink();
    const engine = new PressureEngine(new PressureConfig(), {
      execution_id: "exec-2",
      audit_sink: sink,
      clock: makeScriptedClock([0.0, 0.1, 0.2, 0.3]),
    });
    engine.step(new StepInput({ tool_calls: 1 }));
    expect(engine.pressure).toBeCloseTo(0.06, 9);
    engine.step(new StepInput({ tool_calls: 1 }));
    expect(engine.pressure).toBeCloseTo(0.12, 9);
    engine.step(new StepInput({ tool_calls: 1 }));
    expect(engine.pressure).toBeCloseTo(0.18, 9);
  });

  it("escalates at threshold (inclusive lower bound)", () => {
    const sink = new MemorySink();
    const engine = new PressureEngine(
      new PressureConfig({
        escalation_threshold: 0.5,
        release_threshold: 0.75,
        dissipation_per_step: 0.0,
        depth_coefficient: 0.5,
      }),
      {
        execution_id: "exec-3",
        audit_sink: sink,
        clock: makeScriptedClock([0.0, 0.1]),
      },
    );
    const outcome = engine.step(new StepInput({ depth: 1 }));
    expect(outcome).toBe(StepOutcome.Escalated);
    expect(engine.pressure).toBeCloseTo(0.5, 9);
    expect(engine.lifecycle).toBe(Lifecycle.Escalated);
  });

  it("releases + locks when crossing release_threshold", () => {
    const sink = new MemorySink();
    const engine = new PressureEngine(
      new PressureConfig({
        escalation_threshold: 0.5,
        release_threshold: 0.75,
        dissipation_per_step: 0.0,
        depth_coefficient: 0.75,
      }),
      {
        execution_id: "exec-4",
        audit_sink: sink,
        clock: makeScriptedClock([0.0, 0.1]),
      },
    );
    const outcome = engine.step(new StepInput({ depth: 1 }));
    expect(outcome).toBe(StepOutcome.Released);
    expect(engine.pressure).toBe(0.0);
    expect(engine.lifecycle).toBe(Lifecycle.Locked);

    // Expect init -> step -> release -> locked
    const kinds = sink.events.map((e) => e.kind);
    expect(kinds).toEqual(["engine.init", "engine.step", "engine.release", "engine.locked"]);
  });

  it("rejects steps when locked, without advancing state", () => {
    const sink = new MemorySink();
    const engine = new PressureEngine(
      new PressureConfig({
        escalation_threshold: 0.5,
        release_threshold: 0.75,
        dissipation_per_step: 0.0,
        depth_coefficient: 0.75,
      }),
      {
        execution_id: "exec-5",
        audit_sink: sink,
        clock: makeScriptedClock([0.0, 0.1, 0.2]),
      },
    );
    engine.step(new StepInput({ depth: 1 })); // release+lock
    const snapBefore = engine.snapshot();
    const outcome = engine.step(new StepInput({ tokens: 999, tool_calls: 999 }));
    expect(outcome).toBe(StepOutcome.Locked);
    // step counter did NOT advance
    expect(engine.snapshot().step).toBe(snapBefore.step);
  });

  it("reset() clears pressure and unlocks", () => {
    const sink = new MemorySink();
    const engine = new PressureEngine(
      new PressureConfig({
        escalation_threshold: 0.5,
        release_threshold: 0.75,
        dissipation_per_step: 0.0,
        depth_coefficient: 0.75,
      }),
      {
        execution_id: "exec-6",
        audit_sink: sink,
        clock: makeScriptedClock([0.0, 0.1, 0.2, 0.3]),
      },
    );
    engine.step(new StepInput({ depth: 1 })); // locks
    engine.reset();
    expect(engine.pressure).toBe(0.0);
    expect(engine.lifecycle).toBe(Lifecycle.Init);
    expect(engine.snapshot().step).toBe(0);
  });

  it("clamps pressure to [0, 1]", () => {
    const sink = new MemorySink();
    const engine = new PressureEngine(
      new PressureConfig({
        escalation_threshold: 0.5,
        release_threshold: 0.9,
        dissipation_per_step: 0.0,
        token_coefficient: 1.0,
      }),
      {
        execution_id: "exec-7",
        audit_sink: sink,
        clock: makeScriptedClock([0.0, 0.1]),
      },
    );
    // 100k tokens would produce delta=100.0; clamped
    const outcome = engine.step(new StepInput({ tokens: 100000 }));
    expect(outcome).toBe(StepOutcome.Released);
    expect(engine.pressure).toBe(0.0); // post-release reset
  });

  it("clamps elapsed to non-negative (backwards clock)", () => {
    const sink = new MemorySink();
    const engine = new PressureEngine(
      new PressureConfig({
        dissipation_per_step: 0.0,
        dissipation_per_second: 1.0,
        token_coefficient: 0.0,
        tool_coefficient: 0.08,
        depth_coefficient: 0.0,
      }),
      {
        execution_id: "exec-8",
        audit_sink: sink,
        clock: makeScriptedClock([10.0, 5.0]),
      },
    );
    engine.step(new StepInput({ tool_calls: 1 }));
    // decay should be 0 despite negative elapsed
    expect(engine.pressure).toBeCloseTo(0.08, 9);
  });
});
