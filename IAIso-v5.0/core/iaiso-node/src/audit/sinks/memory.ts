/**
 * Audit sink interface + basic implementations.
 *
 * Mirrors iaiso.audit from the Python reference.
 */

import { AuditEvent } from "../event.js";

export interface AuditSink {
  emit(event: AuditEvent): void | Promise<void>;
  close?(): void | Promise<void>;
}

/** In-memory sink. Useful for tests and conformance runs. */
export class MemorySink implements AuditSink {
  readonly events: AuditEvent[] = [];

  emit(event: AuditEvent): void {
    this.events.push(event);
  }

  clear(): void {
    this.events.length = 0;
  }
}

/** No-op sink. */
export class NullSink implements AuditSink {
  emit(_event: AuditEvent): void {
    // intentionally empty
  }
}

/** Stdout sink: one JSON object per event, newline-delimited. */
export class StdoutSink implements AuditSink {
  emit(event: AuditEvent): void {
    process.stdout.write(event.toJsonString() + "\n");
  }
}

/** Fanout sink: emit each event to every child sink. */
export class FanoutSink implements AuditSink {
  readonly sinks: AuditSink[];

  constructor(sinks: AuditSink[]) {
    this.sinks = sinks;
  }

  async emit(event: AuditEvent): Promise<void> {
    await Promise.all(this.sinks.map((s) => Promise.resolve(s.emit(event))));
  }

  async close(): Promise<void> {
    await Promise.all(
      this.sinks.map((s) => (s.close ? Promise.resolve(s.close()) : Promise.resolve())),
    );
  }
}
