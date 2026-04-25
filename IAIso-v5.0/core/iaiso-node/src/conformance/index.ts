/**
 * Conformance runner — top-level dispatch.
 *
 * Runs every IAIso spec section against this Node reference implementation.
 */

export { runPressureVectors, type VectorResult, makeScriptedClock } from "./pressure.js";
export { runEventsVectors } from "./events.js";
export { runConsentVectors } from "./consent.js";
export { runPolicyVectors } from "./policy.js";

import { runPressureVectors, type VectorResult } from "./pressure.js";
import { runEventsVectors } from "./events.js";
import { runConsentVectors } from "./consent.js";
import { runPolicyVectors } from "./policy.js";

export function runAll(specRoot: string): Record<string, VectorResult[]> {
  return {
    pressure: safeRun(() => runPressureVectors(specRoot), "pressure"),
    consent: safeRun(() => runConsentVectors(specRoot), "consent"),
    events: safeRun(() => runEventsVectors(specRoot), "events"),
    policy: safeRun(() => runPolicyVectors(specRoot), "policy"),
  };
}

function safeRun(fn: () => VectorResult[], section: string): VectorResult[] {
  try {
    return fn();
  } catch (exc) {
    const err = exc as Error;
    if ((err as NodeJS.ErrnoException).code === "ENOENT") {
      return [];
    }
    return [
      {
        section,
        name: "<runner>",
        passed: false,
        message: `${err.name}: ${err.message}`,
      },
    ];
  }
}
