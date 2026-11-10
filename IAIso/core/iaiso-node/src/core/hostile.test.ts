// spec/pressure/hostile.json is shared by every IAIso port.
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { MemorySink } from "../audit/index.js";
import { PressureConfig, PressureEngine, StepInput } from "./engine.js";

const here = dirname(fileURLToPath(import.meta.url));
const hostile = JSON.parse(
  readFileSync(join(here, "..", "..", "spec", "pressure", "hostile.json"), "utf8"),
) as {
  reject: { name: string; field: string; value: unknown }[];
  accept: {
    name: string;
    step: Record<string, number>;
    expect: { pressure: number; outcome: string; lifecycle: string };
  }[];
};

function engine(): PressureEngine {
  return new PressureEngine(new PressureConfig(), {
    execution_id: "hostile",
    audit_sink: new MemorySink(),
    clock: () => 0,
  });
}

describe("hostile StepInput values are refused", () => {
  for (const v of hostile.reject) {
    it(v.name, () => {
      expect(() => engine().step({ [v.field]: v.value } as never)).toThrow(RangeError);
    });
  }
});

describe("extreme StepInput values are handled", () => {
  for (const v of hostile.accept) {
    it(v.name, () => {
      const e = engine();
      const out = e.step(new StepInput(v.step));
      expect(Number.isNaN(e.pressure)).toBe(false);
      expect(e.pressure).toBeCloseTo(v.expect.pressure, 9);
      expect(out).toBe(v.expect.outcome);
      expect(e.lifecycle).toBe(v.expect.lifecycle);
    });
  }
});
