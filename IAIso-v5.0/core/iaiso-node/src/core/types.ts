/**
 * Core type definitions for IAIso.
 *
 * Lifecycle and StepOutcome use const-object-pattern with string literal unions
 * to match the Python reference's enum values on the wire (lowercase strings).
 */

export const Lifecycle = {
  Init: "init",
  Running: "running",
  Escalated: "escalated",
  Released: "released",
  Locked: "locked",
} as const;

export type Lifecycle = (typeof Lifecycle)[keyof typeof Lifecycle];

export const StepOutcome = {
  OK: "ok",
  Escalated: "escalated",
  Released: "released",
  Locked: "locked",
} as const;

export type StepOutcome = (typeof StepOutcome)[keyof typeof StepOutcome];

/**
 * A clock function returning wall-clock or monotonic seconds (with fractional
 * precision). Passed into the engine so tests can script time deterministically.
 */
export type Clock = () => number;

/** Default clock uses `performance.now()` rescaled to seconds. */
export const defaultClock: Clock = () => performance.now() / 1000;
