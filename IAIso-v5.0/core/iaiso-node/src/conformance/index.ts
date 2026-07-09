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
import { setWarnLogger, warnLogger, _resetWarnings } from "../core/engine.js";

/**
 * The vectors deliberately exercise degraded configurations (NullSink,
 * post_release_lock=false, uncalibrated defaults). Their permissive-mode
 * warnings are expected, and printing them would corrupt the suite's output.
 */
function silenceBootWarnings<T>(fn: () => T): T {
  const previous = warnLogger;
  setWarnLogger(() => {});
  try {
    return fn();
  } finally {
    setWarnLogger(previous);
    _resetWarnings();
  }
}

export function runAll(specRoot: string): Record<string, VectorResult[]> {
  return silenceBootWarnings(() => ({
    pressure: safeRun(() => runPressureVectors(specRoot), "pressure"),
    consent: safeRun(() => runConsentVectors(specRoot), "consent"),
    events: safeRun(() => runEventsVectors(specRoot), "events"),
    policy: safeRun(() => runPolicyVectors(specRoot), "policy"),
  }));
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