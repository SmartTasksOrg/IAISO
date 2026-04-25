/**
 * AuditEvent — the event envelope specified in spec/events/README.md §1.
 *
 * Every state change in the engine, coordinator, or consent path emits one of
 * these. The envelope is stable within a MAJOR spec version. Implementations
 * MAY add fields to `data`; consumers MUST ignore unknown fields.
 */

export const SCHEMA_VERSION = "1.0";

export interface AuditEventJSON {
  schema_version: string;
  execution_id: string;
  kind: string;
  timestamp: number;
  data: Record<string, unknown>;
}

export class AuditEvent {
  readonly schemaVersion: string = SCHEMA_VERSION;
  readonly executionId: string;
  readonly kind: string;
  readonly timestamp: number;
  readonly data: Record<string, unknown>;

  constructor(
    executionId: string,
    kind: string,
    timestamp: number,
    data: Record<string, unknown>,
  ) {
    this.executionId = executionId;
    this.kind = kind;
    this.timestamp = timestamp;
    this.data = data;
  }

  toJSON(): AuditEventJSON {
    return {
      schema_version: this.schemaVersion,
      execution_id: this.executionId,
      kind: this.kind,
      timestamp: this.timestamp,
      data: this.data,
    };
  }

  toJsonString(): string {
    return JSON.stringify(this.toJSON());
  }
}
