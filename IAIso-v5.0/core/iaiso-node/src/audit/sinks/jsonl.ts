/**
 * JSONL file sink — appends one JSON event per line.
 *
 * Matches iaiso.audit.JsonlFileSink in the Python reference.
 */

import { appendFileSync } from "node:fs";
import type { AuditSink } from "./memory.js";
import type { AuditEvent } from "../event.js";

export class JsonlFileSink implements AuditSink {
  constructor(public readonly path: string) {}

  emit(event: AuditEvent): void {
    appendFileSync(this.path, event.toJsonString() + "\n", "utf8");
  }
}
