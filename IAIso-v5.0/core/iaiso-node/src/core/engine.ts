/**
 * Core pressure-accumulation model.
 *
 * Port of the Python reference implementation. See
 * ../../../spec/pressure/README.md for the normative specification.
 *
 * Floating-point equality is within 1e-9 absolute tolerance; this port is
 * expected to pass every vector in ../../../spec/pressure/vectors.json.
 */

import { AuditEvent } from "../audit/event.js";
import type { AuditSink } from "../audit/sinks/memory.js";
import { NullSink } from "../audit/sinks/memory.js";
import { Lifecycle, StepOutcome, defaultClock } from "./types.js";
import type { Clock } from "./types.js";

export type EnforcementMode = "permissive" | "strict";
export const ENFORCEMENT_PERMISSIVE: EnforcementMode = "permissive";
export const ENFORCEMENT_STRICT: EnforcementMode = "strict";

/**
 * Thrown when `enforcement_mode: "strict"` refuses a degraded configuration.
 *
 * Fail closed. A safety framework whose gates silently do nothing is worse
 * than no framework, because it produces confidence.
 */
export class StrictModeError extends Error {
  constructor(message: string) {
    super(`iaiso: strict mode — ${message}`);
    this.name = "StrictModeError";
  }
}

/** Coefficient set shipped with the library. Matching it means nobody calibrated. */
const LIBRARY_DEFAULT_COEFFICIENTS: Record<string, number> = {
  token_coefficient: 0.015,
  tool_coefficient: 0.08,
  depth_coefficient: 0.05,
  dissipation_per_step: 0.02,
  dissipation_per_second: 0.0,
  escalation_threshold: 0.85,
  release_threshold: 0.95,
};

const warned = new Set<string>();

/** Route permissive-mode degradation warnings. Replaceable; never silent by default. */
export let warnLogger: (message: string) => void = (message) => {
  console.warn(message);
};

export function setWarnLogger(fn: (message: string) => void): void {
  warnLogger = fn;
}

/** Reset the once-per-process warning memo. Test helper. */
export function _resetWarnings(): void {
  warned.clear();
}

function degraded(condition: string, message: string, mode: EnforcementMode): void {
  if (mode === ENFORCEMENT_STRICT) {
    throw new StrictModeError(message);
  }
  if (!warned.has(condition)) {
    warned.add(condition);
    warnLogger(`iaiso: ${message}`);
  }
}

export interface PressureConfigInput {
  escalation_threshold?: number;
  release_threshold?: number;
  dissipation_per_step?: number;
  dissipation_per_second?: number;
  token_coefficient?: number;
  tool_coefficient?: number;
  depth_coefficient?: number;
  post_release_lock?: boolean;
  /** USD per 1M tokens, keyed by model name. Enables `spend_usd` on events. */
  model_costs?: Record<string, number>;
  /** Hard USD ceiling; 0 disables. Exceeding it reuses the lock path. */
  budget_usd?: number;
}

/**
 * PressureConfig. Default coefficients produce reasonable behavior on the
 * reference scenarios; calibrate for your workload before relying on specific
 * threshold values. See spec/pressure/README.md §2 for normative ranges and
 * validation rules.
 */
export class PressureConfig {
  readonly escalation_threshold: number;
  readonly release_threshold: number;
  readonly dissipation_per_step: number;
  readonly dissipation_per_second: number;
  readonly token_coefficient: number;
  readonly tool_coefficient: number;
  readonly depth_coefficient: number;
  readonly post_release_lock: boolean;
  readonly model_costs: Record<string, number> | null;
  readonly budget_usd: number;

  constructor(input: PressureConfigInput = {}) {
    this.escalation_threshold = input.escalation_threshold ?? 0.85;
    this.release_threshold = input.release_threshold ?? 0.95;
    this.dissipation_per_step = input.dissipation_per_step ?? 0.02;
    this.dissipation_per_second = input.dissipation_per_second ?? 0.0;
    this.token_coefficient = input.token_coefficient ?? 0.015;
    this.tool_coefficient = input.tool_coefficient ?? 0.08;
    this.depth_coefficient = input.depth_coefficient ?? 0.05;
    this.post_release_lock = input.post_release_lock ?? true;
    this.model_costs = input.model_costs ?? null;
    this.budget_usd = input.budget_usd ?? 0.0;

    this._validate();
  }

  private _validate(): void {
    if (this.escalation_threshold < 0.0 || this.escalation_threshold > 1.0) {
      throw new RangeError("escalation_threshold must be in [0, 1]");
    }
    if (this.release_threshold < 0.0 || this.release_threshold > 1.0) {
      throw new RangeError("release_threshold must be in [0, 1]");
    }
    if (this.release_threshold <= this.escalation_threshold) {
      throw new RangeError("release_threshold must exceed escalation_threshold");
    }
    const nonNegativeFields = [
      "dissipation_per_step",
      "dissipation_per_second",
      "token_coefficient",
      "tool_coefficient",
      "depth_coefficient",
    ] as const;
    for (const f of nonNegativeFields) {
      if (this[f] < 0) {
        throw new RangeError(`${f} must be non-negative`);
      }
    }
    if (this.budget_usd < 0) {
      throw new RangeError("budget_usd must be non-negative");
    }
    for (const [model, price] of Object.entries(this.model_costs ?? {})) {
      if (price < 0) {
        throw new RangeError(`model_costs[${model}] must be non-negative`);
      }
    }
  }

  /** True when nothing has been calibrated away from library defaults. */
  is_default_coefficients(): boolean {
    return Object.entries(LIBRARY_DEFAULT_COEFFICIENTS).every(
      ([name, value]) => (this as unknown as Record<string, number>)[name] === value,
    );
  }
}

export interface StepInputInput {
  tokens?: number;
  tool_calls?: number;
  depth?: number;
  tag?: string | null;
  /** Prices `tokens` against `PressureConfig.model_costs`. Unpriced = unmetered. */
  model?: string | null;
}

export class StepInput {
  readonly tokens: number;
  readonly tool_calls: number;
  readonly depth: number;
  readonly tag: string | null;
  readonly model: string | null;

  constructor(input: StepInputInput = {}) {
    this.tokens = input.tokens ?? 0;
    this.tool_calls = input.tool_calls ?? 0;
    this.depth = input.depth ?? 0;
    this.tag = input.tag ?? null;
    this.model = input.model ?? null;
  }
}

export interface PressureSnapshot {
  pressure: number;
  step: number;
  lifecycle: Lifecycle;
  last_delta: number;
  last_step_at: number;
}

export interface PressureEngineOptions {
  execution_id: string;
  audit_sink?: AuditSink;
  clock?: Clock;
  /** Timestamp source for emitted AuditEvents. Defaults to Date.now()/1000. */
  timestampClock?: Clock;
  enforcement_mode?: EnforcementMode;
  calibration_artifact?: string;
  consent_algorithm?: string;
  consent_key_auto_generated?: boolean;
}

export class PressureEngine {
  private readonly _cfg: PressureConfig;
  private readonly _executionId: string;
  private readonly _audit: AuditSink;
  private readonly _clock: Clock;
  private readonly _timestampClock: Clock;

  private _pressure: number = 0.0;
  private _step: number = 0;
  private _lifecycle: Lifecycle = Lifecycle.Init;
  private _lastDelta: number = 0.0;
  private _lastStepAt: number;
  private _spendUsd: number = 0.0;
  private readonly _enforcementMode: EnforcementMode;

  constructor(config: PressureConfig, opts: PressureEngineOptions) {
    const mode = opts.enforcement_mode ?? ENFORCEMENT_PERMISSIVE;
    if (mode !== ENFORCEMENT_PERMISSIVE && mode !== ENFORCEMENT_STRICT) {
      throw new RangeError(
        `enforcement_mode must be "permissive" or "strict", got ${JSON.stringify(mode)}`,
      );
    }
    this._enforcementMode = mode;

    // Boot guard runs before any state exists, so a strict refusal leaves
    // nothing half-constructed behind — and emits no engine.init.
    PressureEngine._bootGuard(config, opts, mode);

    this._cfg = config;
    this._executionId = opts.execution_id;
    this._audit = opts.audit_sink ?? new NullSink();
    this._clock = opts.clock ?? defaultClock;
    this._timestampClock = opts.timestampClock ?? (() => Date.now() / 1000);

    this._lastStepAt = this._clock();
    this._emit("engine.init", { pressure: this._pressure });
  }

  private static _bootGuard(
    config: PressureConfig,
    opts: PressureEngineOptions,
    mode: EnforcementMode,
  ): void {
    if (opts.consent_algorithm === "HS256" && opts.consent_key_auto_generated) {
      degraded(
        "consent_autogen_hs256",
        "consent algorithm is HS256 and the signing key was auto-generated; " +
          "no other party can verify these tokens. Supply a key, switch to " +
          "RS256, or set enforcement_mode: permissive.",
        mode,
      );
    }
    if (opts.audit_sink === undefined || opts.audit_sink instanceof NullSink) {
      degraded(
        "null_sink",
        "audit sink is NullSink; escalations would be unobservable. " +
          "Configure a sink or set enforcement_mode: permissive.",
        mode,
      );
    }
    if (!config.post_release_lock) {
      degraded(
        "post_release_lock_false",
        "post_release_lock is false; a released execution resumes immediately. " +
          "Set post_release_lock: true or set enforcement_mode: permissive.",
        mode,
      );
    }
    if (config.is_default_coefficients() && !opts.calibration_artifact) {
      degraded(
        "uncalibrated_defaults",
        "coefficients are at library defaults and no calibration artifact is " +
          "present; thresholds will either never fire or fire constantly. " +
          "Calibrate, or set enforcement_mode: permissive.",
        mode,
      );
    }
  }

  get enforcement_mode(): EnforcementMode {
    return this._enforcementMode;
  }

  /** Cumulative USD spent by this execution, per `model_costs`. */
  get spend_usd(): number {
    return this._spendUsd;
  }

  get config(): PressureConfig {
    return this._cfg;
  }

  get execution_id(): string {
    return this._executionId;
  }

  get pressure(): number {
    return this._pressure;
  }

  get lifecycle(): Lifecycle {
    return this._lifecycle;
  }

  snapshot(): PressureSnapshot {
    return {
      pressure: this._pressure,
      step: this._step,
      lifecycle: this._lifecycle,
      last_delta: this._lastDelta,
      last_step_at: this._lastStepAt,
    };
  }

  /**
   * Account for a unit of work and advance the engine.
   * See spec/pressure/README.md §4–§6.
   */
  step(work: StepInput | StepInputInput): StepOutcome {
    const w = work instanceof StepInput ? work : new StepInput(work);

    if (this._lifecycle === Lifecycle.Locked) {
      this._emit("engine.step.rejected", {
        reason: "locked",
        requested_tokens: w.tokens,
        requested_tools: w.tool_calls,
      });
      return StepOutcome.Locked;
    }

    const now = this._clock();
    const elapsed = Math.max(0.0, now - this._lastStepAt);

    const delta =
      (w.tokens / 1000.0) * this._cfg.token_coefficient +
      w.tool_calls * this._cfg.tool_coefficient +
      w.depth * this._cfg.depth_coefficient;
    const decay =
      this._cfg.dissipation_per_step +
      elapsed * this._cfg.dissipation_per_second;

    this._pressure = Math.max(0.0, Math.min(1.0, this._pressure + delta - decay));
    this._step += 1;
    this._lastDelta = delta - decay;
    this._lastStepAt = now;
    this._lifecycle = Lifecycle.Running;

    this._spendUsd += this._price(w);

    const eventData: Record<string, unknown> = {
      step: this._step,
      pressure: this._pressure,
      delta,
      decay,
      tokens: w.tokens,
      tool_calls: w.tool_calls,
      depth: w.depth,
      tag: w.tag,
    };
    // `spend_usd` appears only when prices are configured, so consumers of the
    // frozen 1.0 envelope never see a key they did not opt into.
    if (this._cfg.model_costs) {
      eventData["spend_usd"] = this._spendUsd;
    }
    this._emit("engine.step", eventData);

    // Budget exhaustion reuses the existing lock path. No new lifecycle state:
    // the wire format is frozen.
    if (this._cfg.budget_usd > 0 && this._spendUsd >= this._cfg.budget_usd) {
      return this._lockForBudget();
    }

    if (this._pressure >= this._cfg.release_threshold) {
      return this._release();
    }
    if (this._pressure >= this._cfg.escalation_threshold) {
      this._lifecycle = Lifecycle.Escalated;
      this._emit("engine.escalation", {
        pressure: this._pressure,
        threshold: this._cfg.escalation_threshold,
      });
      return StepOutcome.Escalated;
    }
    return StepOutcome.OK;
  }

  /** USD for this step. Unpriced or unnamed models cost nothing. */
  private _price(w: StepInput): number {
    const costs = this._cfg.model_costs;
    if (!costs || w.model === null) {
      return 0.0;
    }
    const pricePerMillion = costs[w.model];
    if (pricePerMillion === undefined) {
      return 0.0;
    }
    return (w.tokens / 1_000_000.0) * pricePerMillion;
  }

  private _lockForBudget(): StepOutcome {
    this._pressure = 0.0;
    this._lifecycle = Lifecycle.Locked;
    this._emit("engine.locked", {
      reason: "budget_exceeded",
      spend_usd: this._spendUsd,
      budget_usd: this._cfg.budget_usd,
    });
    return StepOutcome.Locked;
  }

  private _release(): StepOutcome {
    const priorPressure = this._pressure;
    this._lifecycle = Lifecycle.Released;
    this._emit("engine.release", {
      pressure: priorPressure,
      threshold: this._cfg.release_threshold,
    });

    this._pressure = 0.0;
    if (this._cfg.post_release_lock) {
      this._lifecycle = Lifecycle.Locked;
      this._emit("engine.locked", { reason: "post_release_lock" });
    } else {
      this._lifecycle = Lifecycle.Running;
    }
    return StepOutcome.Released;
  }

  /**
   * Clear pressure and unlock. Emits `engine.reset`.
   *
   * Spend is cleared with the rest of the state: a reset is a human deciding
   * this execution starts over, budget included.
   */
  reset(): PressureSnapshot {
    this._pressure = 0.0;
    this._step = 0;
    this._lastDelta = 0.0;
    this._lastStepAt = this._clock();
    this._lifecycle = Lifecycle.Init;
    this._spendUsd = 0.0;
    this._emit("engine.reset", { pressure: this._pressure });
    return this.snapshot();
  }

  private _emit(kind: string, data: Record<string, unknown>): void {
    this._audit.emit(
      new AuditEvent(this._executionId, kind, this._timestampClock(), data),
    );
  }
}