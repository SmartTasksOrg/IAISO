/**
 * Conformance runner — events vectors.
 *
 * Validates emitted event streams against the expectations in
 * spec/events/vectors.json. Compares schema_version, execution_id, kind,
 * and the payload fields explicitly listed in each expected event;
 * ignores timestamps and extra implementation-specific fields.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { AuditEvent } from "../audit/event.js";
import { MemorySink } from "../audit/sinks/memory.js";
import { PressureConfig, PressureEngine, StepInput } from "../core/engine.js";
import type { Clock } from "../core/types.js";
import type { VectorResult } from "./pressure.js";

interface EventsVector {
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
  reset_after_step?: number;
  clock_after_reset?: number;
  execution_id?: string;
  expected_events: Array<{
    schema_version?: string;
    execution_id?: string;
    kind?: string;
    data?: Record<string, unknown>;
  }>;
  strict_length?: boolean;
}

interface EventsVectorFile {
  version: string;
  tolerance?: number;
  vectors: EventsVector[];
}

export function runEventsVectors(specRoot: string): VectorResult[] {
  const data = JSON.parse(
    readFileSync(join(specRoot, "events", "vectors.json"), "utf8"),
  ) as EventsVectorFile;
  const tolerance = data.tolerance ?? 1e-9;
  const results: VectorResult[] = [];

  for (const vec of data.vectors) {
    try {
      results.push(runOneVector(vec, tolerance));
    } catch (exc) {
      results.push({
        section: "events",
        name: vec.name,
        passed: false,
        message: `runner exception: ${(exc as Error).name}: ${(exc as Error).message}`,
      });
    }
  }

  return results;
}

function runOneVector(vec: EventsVector, tolerance: number): VectorResult {
  const config = new PressureConfig(vec.config ?? {});
  const scripted = [...(vec.clock ?? [0.0])];
  let ci = 0;
  const clock: Clock = () => {
    if (ci >= scripted.length) throw new Error("clock exhausted");
    return scripted[ci++]!;
  };
  const audit = new MemorySink();
  const executionId = vec.execution_id ?? `exec-events-${vec.name}`;

  const engine = new PressureEngine(config, {
    execution_id: executionId,
    audit_sink: audit,
    clock,
  });

  const steps = vec.steps ?? [];
  for (let i = 0; i < steps.length; i++) {
    const s = steps[i]!;
    engine.step(
      new StepInput({
        tokens: s.tokens ?? 0,
        tool_calls: s.tool_calls ?? 0,
        depth: s.depth ?? 0,
        tag: s.tag ?? null,
      }),
    );
    if (vec.reset_after_step === i + 1) {
      if (vec.clock_after_reset !== undefined) {
        scripted.splice(ci, 0, vec.clock_after_reset);
      }
      engine.reset();
    }
  }

  const emitted = audit.events;
  const expected = vec.expected_events;
  const strict = vec.strict_length ?? true;

  if (emitted.length < expected.length) {
    return {
      section: "events",
      name: vec.name,
      passed: false,
      message: `expected at least ${expected.length} events, got ${emitted.length}`,
    };
  }
  if (strict && emitted.length !== expected.length) {
    return {
      section: "events",
      name: vec.name,
      passed: false,
      message: `expected exactly ${expected.length} events, got ${emitted.length}`,
    };
  }

  for (let i = 0; i < expected.length; i++) {
    const a = emitted[i]!;
    const e = expected[i]!;
    const mismatch = compareEvent(a, e, tolerance);
    if (mismatch) {
      return {
        section: "events",
        name: vec.name,
        passed: false,
        message: `event[${i}] (${e.kind ?? "?"}): ${mismatch}`,
      };
    }
  }

  return { section: "events", name: vec.name, passed: true, message: "" };
}

function compareEvent(
  actual: AuditEvent,
  expected: {
    schema_version?: string;
    execution_id?: string;
    kind?: string;
    data?: Record<string, unknown>;
  },
  tolerance: number,
): string | null {
  if (expected.schema_version !== undefined && actual.schemaVersion !== expected.schema_version) {
    return `schema_version: expected ${JSON.stringify(expected.schema_version)}, got ${JSON.stringify(actual.schemaVersion)}`;
  }
  if (expected.execution_id !== undefined && actual.executionId !== expected.execution_id) {
    return `execution_id: expected ${JSON.stringify(expected.execution_id)}, got ${JSON.stringify(actual.executionId)}`;
  }
  if (expected.kind !== undefined && actual.kind !== expected.kind) {
    return `kind: expected ${JSON.stringify(expected.kind)}, got ${JSON.stringify(actual.kind)}`;
  }

  const expectedData = expected.data ?? {};
  for (const [k, v] of Object.entries(expectedData)) {
    if (!(k in actual.data)) {
      return `data missing required key ${JSON.stringify(k)}`;
    }
    const av = actual.data[k];
    if (typeof v === "number" && typeof av === "number") {
      if (Math.abs(av - v) > tolerance) {
        return `data.${k}: expected ${JSON.stringify(v)}, got ${JSON.stringify(av)}`;
      }
    } else if (JSON.stringify(av) !== JSON.stringify(v)) {
      return `data.${k}: expected ${JSON.stringify(v)}, got ${JSON.stringify(av)}`;
    }
  }

  return null;
}
