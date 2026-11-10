/**
 * Conformance runner — pressure vectors.
 *
 * Loads spec/pressure/vectors.json and runs each vector against the Node
 * reference implementation. Must pass all 20 vectors.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { MemorySink } from "../audit/sinks/memory.js";
import { PressureConfig, PressureEngine, StepInput } from "../core/engine.js";
import type { Clock } from "../core/types.js";

export interface VectorResult {
  section: string;
  name: string;
  passed: boolean;
  message: string;
}

/** Produce a scripted clock that returns predetermined values in order. */
export function makeScriptedClock(values: number[]): Clock {
  const scripted = [...values];
  let i = 0;
  return () => {
    if (i >= scripted.length) {
      throw new Error(
        `ScriptedClock exhausted after ${i} calls; impl consumed more clock values than the vector specified`,
      );
    }
    return scripted[i++]!;
  };
}

function approxEqual(a: unknown, b: unknown, tolerance: number): boolean {
  if (typeof a === "number" && typeof b === "number") {
    return Math.abs(a - b) <= tolerance;
  }
  return a === b;
}

interface PressureVector {
  name: string;
  description?: string;
  config?: Record<string, unknown>;
  clock?: number[];
  steps?: Array<{
    tokens?: number;
    tool_calls?: number;
    depth?: number;
    tag?: string | null;
  }>;
  expected_initial?: Record<string, unknown>;
  expected_steps?: Array<Record<string, unknown>>;
  reset_after_step?: number;
  clock_after_reset?: number;
  expected_after_reset?: Record<string, unknown>;
  expect_config_error?: string;
}

interface PressureVectorFile {
  version: string;
  tolerance?: number;
  vectors: PressureVector[];
}

export function runPressureVectors(specRoot: string): VectorResult[] {
  const raw = readFileSync(
    join(specRoot, "pressure", "vectors.json"),
    "utf8",
  );
  const data = JSON.parse(raw) as PressureVectorFile;
  const tolerance = data.tolerance ?? 1e-9;
  const results: VectorResult[] = [];

  for (const vec of data.vectors) {
    if (vec.expect_config_error !== undefined) {
      results.push(runConfigErrorVector(vec));
      continue;
    }
    try {
      results.push(runTrajectoryVector(vec, tolerance));
    } catch (exc) {
      results.push({
        section: "pressure",
        name: vec.name,
        passed: false,
        message: `runner exception: ${(exc as Error).name}: ${(exc as Error).message}`,
      });
    }
  }

  return results;
}

function runConfigErrorVector(vec: PressureVector): VectorResult {
  const expected = vec.expect_config_error!;
  try {
    new PressureConfig(vec.config ?? {});
  } catch (exc) {
    const msg = (exc as Error).message;
    if (msg.includes(expected)) {
      return { section: "pressure", name: vec.name, passed: true, message: "" };
    }
    return {
      section: "pressure",
      name: vec.name,
      passed: false,
      message: `got error ${JSON.stringify(msg)} but expected substring ${JSON.stringify(expected)}`,
    };
  }
  return {
    section: "pressure",
    name: vec.name,
    passed: false,
    message: `expected config validation error containing ${JSON.stringify(expected)} but config was accepted`,
  };
}

function runTrajectoryVector(vec: PressureVector, tolerance: number): VectorResult {
  const config = new PressureConfig(vec.config ?? {});
  const clockValues = vec.clock ?? [0.0];
  // Mutable array so reset-time injection works
  const scripted: number[] = [...clockValues];
  let clockIndex = 0;
  const clock: Clock = () => {
    if (clockIndex >= scripted.length) {
      throw new Error(
        `ScriptedClock exhausted after ${clockIndex} calls`,
      );
    }
    return scripted[clockIndex++]!;
  };
  const audit = new MemorySink();

  const engine = new PressureEngine(config, {
    execution_id: `conformance-${vec.name}`,
    audit_sink: audit,
    clock,
  });

  if (vec.expected_initial) {
    const snap = engine.snapshot() as unknown as Record<string, unknown>;
    for (const [k, expected] of Object.entries(vec.expected_initial)) {
      if (!approxEqual(snap[k], expected, tolerance)) {
        return failure(
          vec,
          `initial ${k}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(snap[k])}`,
        );
      }
    }
  }

  const steps = vec.steps ?? [];
  const expectedSteps = vec.expected_steps ?? [];

  for (let i = 0; i < steps.length; i++) {
    const stepInput = steps[i]!;
    const outcome = engine.step(
      new StepInput({
        tokens: stepInput.tokens ?? 0,
        tool_calls: stepInput.tool_calls ?? 0,
        depth: stepInput.depth ?? 0,
        tag: stepInput.tag ?? null,
      }),
    );
    const expected = expectedSteps[i];
    if (!expected) continue;

    if ("pressure" in expected) {
      if (!approxEqual(engine.pressure, expected.pressure, tolerance)) {
        return failure(
          vec,
          `step ${i + 1}: pressure expected ${JSON.stringify(expected.pressure)}, got ${engine.pressure}`,
        );
      }
    }
    if ("outcome" in expected) {
      if (outcome !== expected.outcome) {
        return failure(
          vec,
          `step ${i + 1}: outcome expected ${JSON.stringify(expected.outcome)}, got ${JSON.stringify(outcome)}`,
        );
      }
    }
    if ("lifecycle" in expected) {
      if (engine.lifecycle !== expected.lifecycle) {
        return failure(
          vec,
          `step ${i + 1}: lifecycle expected ${JSON.stringify(expected.lifecycle)}, got ${JSON.stringify(engine.lifecycle)}`,
        );
      }
    }
    if ("step" in expected) {
      if (engine.snapshot().step !== expected.step) {
        return failure(
          vec,
          `step ${i + 1}: step counter expected ${JSON.stringify(expected.step)}, got ${engine.snapshot().step}`,
        );
      }
    }

    // delta / decay via engine.step events
    if ("delta" in expected || "decay" in expected) {
      const stepEvents = audit.events.filter((e) => e.kind === "engine.step");
      const latest = stepEvents[stepEvents.length - 1];
      if (latest) {
        if ("delta" in expected) {
          const d = latest.data["delta"] as number;
          if (!approxEqual(d, expected.delta, tolerance)) {
            return failure(
              vec,
              `step ${i + 1}: delta expected ${JSON.stringify(expected.delta)}, got ${d}`,
            );
          }
        }
        if ("decay" in expected) {
          const d = latest.data["decay"] as number;
          if (!approxEqual(d, expected.decay, tolerance)) {
            return failure(
              vec,
              `step ${i + 1}: decay expected ${JSON.stringify(expected.decay)}, got ${d}`,
            );
          }
        }
      }
    }

    if (vec.reset_after_step === i + 1) {
      if (vec.clock_after_reset !== undefined) {
        scripted.splice(clockIndex, 0, vec.clock_after_reset);
      }
      engine.reset();
    }
  }

  if (vec.expected_after_reset) {
    const snap = engine.snapshot() as unknown as Record<string, unknown>;
    for (const [k, expected] of Object.entries(vec.expected_after_reset)) {
      if (!approxEqual(snap[k], expected, tolerance)) {
        return failure(
          vec,
          `post-reset ${k}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(snap[k])}`,
        );
      }
    }
  }

  return { section: "pressure", name: vec.name, passed: true, message: "" };
}

function failure(vec: PressureVector, message: string): VectorResult {
  return { section: "pressure", name: vec.name, passed: false, message };
}
