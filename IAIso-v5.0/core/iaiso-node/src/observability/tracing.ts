/**
 * OpenTelemetry tracing integration.
 *
 * Provides an `OtelSpanSink` that opens a span per execution and
 * attaches every audit event as a span event. Install `@opentelemetry/api`
 * in the host application; this module is structurally typed so the
 * dependency stays optional.
 *
 * Install:
 *   npm install @opentelemetry/api
 *   # (plus your preferred SDK, e.g. @opentelemetry/sdk-node)
 *
 * Usage:
 *   import { trace } from "@opentelemetry/api";
 *   import { OtelSpanSink } from "@iaiso/core/observability/tracing";
 *
 *   const sink = new OtelSpanSink({
 *     tracer: trace.getTracer("iaiso"),
 *   });
 */

import type { AuditSink } from "../audit/sinks/memory.js";
import type { AuditEvent } from "../audit/event.js";

// Structural types for the subset of @opentelemetry/api we use.
interface SpanLike {
  addEvent(name: string, attributes?: Record<string, unknown>, time?: number): void;
  setAttribute(key: string, value: unknown): void;
  end(endTime?: number): void;
  recordException?(exception: unknown): void;
}

interface TracerLike {
  startSpan(
    name: string,
    options?: { attributes?: Record<string, unknown> },
  ): SpanLike;
}

export interface OtelSpanSinkOptions {
  tracer: TracerLike;
  /** Optional base span name; per-execution spans become `${baseName}.<execution_id>`. */
  spanName?: string;
}

/**
 * Audit sink that opens one OTel span per execution and attaches every
 * subsequent audit event as a span event, closing the span on
 * `execution.closed`.
 */
export class OtelSpanSink implements AuditSink {
  readonly tracer: TracerLike;
  readonly spanName: string;
  private readonly _spans = new Map<string, SpanLike>();

  constructor(opts: OtelSpanSinkOptions) {
    this.tracer = opts.tracer;
    this.spanName = opts.spanName ?? "iaiso.execution";
  }

  emit(event: AuditEvent): void {
    let span = this._spans.get(event.executionId);

    if (!span && event.kind === "engine.init") {
      span = this.tracer.startSpan(
        `${this.spanName}:${event.executionId}`,
        { attributes: { "iaiso.execution_id": event.executionId } },
      );
      this._spans.set(event.executionId, span);
    }

    if (!span) {
      // No open span for this execution; drop quietly to avoid
      // surprising the host with unattributed spans.
      return;
    }

    span.addEvent(
      event.kind,
      {
        ...event.data,
        "iaiso.schema_version": event.schemaVersion,
      },
      // OTel uses milliseconds-since-epoch for event timestamps
      event.timestamp * 1000,
    );

    // Mirror headline state onto the span itself for easier querying
    if (event.kind === "engine.step") {
      const p = event.data["pressure"];
      if (typeof p === "number") {
        span.setAttribute("iaiso.pressure", p);
      }
    }
    if (event.kind === "engine.escalation") {
      span.setAttribute("iaiso.escalated", true);
    }
    if (event.kind === "engine.release") {
      span.setAttribute("iaiso.released", true);
    }

    if (event.kind === "execution.closed") {
      span.end(event.timestamp * 1000);
      this._spans.delete(event.executionId);
    }
  }

  /** Close any spans that were never explicitly ended (on shutdown). */
  close(): void {
    for (const [id, span] of this._spans) {
      span.end();
      this._spans.delete(id);
    }
  }
}
