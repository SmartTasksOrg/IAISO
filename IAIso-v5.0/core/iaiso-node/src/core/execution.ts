/**
 * BoundedExecution — high-level facade combining engine + consent + audit.
 *
 * Node idiomatic usage:
 *
 *   await BoundedExecution.run(
 *     { config: new PressureConfig(), consent, auditSink },
 *     async (exec) => {
 *       while (!done) {
 *         if (exec.check() === "escalated") {
 *           await escalateToHuman();
 *           exec.reset();
 *           continue;
 *         }
 *         exec.requireScope("tools.search");
 *         const result = await runTool("search", query);
 *         exec.recordToolCall({ name: "search" });
 *         exec.recordTokens(result.tokenCount, "search_result");
 *       }
 *     },
 *   );
 *
 * Or explicit lifecycle:
 *   const exec = BoundedExecution.start({ config: new PressureConfig() });
 *   try { ... } finally { exec.close(); }
 */

import { randomUUID } from "node:crypto";

import { AuditEvent } from "../audit/event.js";
import type { AuditSink } from "../audit/sinks/memory.js";
import { NullSink } from "../audit/sinks/memory.js";
import type { ConsentScope } from "../consent/index.js";
import { InsufficientScope } from "../consent/index.js";
import {
  Lifecycle,
  StepOutcome,
} from "./types.js";
import type { Clock } from "./types.js";
import {
  PressureConfig,
  PressureEngine,
  StepInput,
} from "./engine.js";
import type { PressureSnapshot } from "./engine.js";

export class ExecutionLocked extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ExecutionLocked";
  }
}

export class ScopeRequired extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ScopeRequired";
  }
}

export interface BoundedExecutionOptions {
  execution_id?: string;
  config?: PressureConfig;
  consent?: ConsentScope | null;
  audit_sink?: AuditSink;
  clock?: Clock;
  timestampClock?: Clock;
}

export class BoundedExecution {
  readonly engine: PressureEngine;
  consent: ConsentScope | null;
  readonly audit_sink: AuditSink;
  private readonly _timestampClock: Clock;
  private _closed = false;

  private constructor(
    engine: PressureEngine,
    consent: ConsentScope | null,
    audit_sink: AuditSink,
    timestampClock: Clock,
  ) {
    this.engine = engine;
    this.consent = consent;
    this.audit_sink = audit_sink;
    this._timestampClock = timestampClock;
  }

  static start(opts: BoundedExecutionOptions = {}): BoundedExecution {
    const execId = opts.execution_id ?? `exec-${randomUUID()}`;
    const cfg = opts.config ?? new PressureConfig();
    const sink = opts.audit_sink ?? new NullSink();
    const tsClock = opts.timestampClock ?? (() => Date.now() / 1000);
    const engine = new PressureEngine(cfg, {
      execution_id: execId,
      audit_sink: sink,
      clock: opts.clock,
      timestampClock: tsClock,
    });

    const instance = new BoundedExecution(
      engine,
      opts.consent ?? null,
      sink,
      tsClock,
    );
    if (opts.consent) {
      instance._emit("execution.consent_attached", {
        subject: opts.consent.subject,
        scopes: opts.consent.scopes,
        jti: opts.consent.jti,
      });
    }
    return instance;
  }

  /**
   * Run a callback with a BoundedExecution, emitting `execution.closed` on
   * exit (with exception type if the callback throws).
   */
  static async run<T>(
    opts: BoundedExecutionOptions,
    fn: (exec: BoundedExecution) => Promise<T> | T,
  ): Promise<T> {
    const exec = BoundedExecution.start(opts);
    let thrownName: string | null = null;
    try {
      return await fn(exec);
    } catch (err) {
      thrownName =
        err instanceof Error ? err.name : typeof err === "object" ? "Object" : typeof err;
      throw err;
    } finally {
      exec.close(thrownName);
    }
  }

  recordTokens(tokens: number, tag: string | null = null): StepOutcome {
    return this._account(new StepInput({ tokens, tag }));
  }

  recordToolCall(
    params: { name?: string | null; count?: number; tokens?: number } = {},
  ): StepOutcome {
    return this._account(
      new StepInput({
        tokens: params.tokens ?? 0,
        tool_calls: params.count ?? 1,
        tag: params.name ?? null,
      }),
    );
  }

  recordStep(
    params: {
      tokens?: number;
      tool_calls?: number;
      depth?: number;
      tag?: string | null;
    } = {},
  ): StepOutcome {
    return this._account(
      new StepInput({
        tokens: params.tokens ?? 0,
        tool_calls: params.tool_calls ?? 0,
        depth: params.depth ?? 0,
        tag: params.tag ?? null,
      }),
    );
  }

  private _account(work: StepInput): StepOutcome {
    const outcome = this.engine.step(work);
    if (outcome === StepOutcome.Locked) {
      throw new ExecutionLocked(
        `execution ${this.engine.execution_id} is locked; call reset() before continuing`,
      );
    }
    return outcome;
  }

  /** Return the current outcome without advancing. Safe guard for agent-loop tops. */
  check(): StepOutcome {
    const lc = this.engine.lifecycle;
    if (lc === Lifecycle.Locked) return StepOutcome.Locked;
    if (lc === Lifecycle.Escalated) return StepOutcome.Escalated;
    return StepOutcome.OK;
  }

  /**
   * Require the attached consent to grant `scope`. Emits `consent.granted`
   * or `consent.denied` accordingly.
   */
  requireScope(scope: string): void {
    if (this.consent == null) {
      this._emit("consent.missing", { requested: scope });
      throw new ScopeRequired(
        `scope '${scope}' required but no consent attached`,
      );
    }
    try {
      this.consent.require(scope);
    } catch (err) {
      if (err instanceof InsufficientScope) {
        this._emit("consent.denied", {
          requested: scope,
          granted: this.consent.scopes,
          jti: this.consent.jti,
        });
      }
      throw err;
    }
    this._emit("consent.granted", {
      requested: scope,
      jti: this.consent.jti,
    });
  }

  reset(): PressureSnapshot {
    return this.engine.reset();
  }

  snapshot(): PressureSnapshot {
    return this.engine.snapshot();
  }

  close(exception: string | null = null): void {
    if (this._closed) return;
    this._closed = true;
    this._emit("execution.closed", {
      final_pressure: this.engine.pressure,
      final_lifecycle: this.engine.lifecycle,
      exception,
    });
  }

  private _emit(kind: string, data: Record<string, unknown>): void {
    this.audit_sink.emit(
      new AuditEvent(
        this.engine.execution_id,
        kind,
        this._timestampClock(),
        data,
      ),
    );
  }
}
