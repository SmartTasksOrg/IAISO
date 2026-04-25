/**
 * Sumo Logic HTTP Source sink.
 *
 * Sumo Logic docs:
 *   https://help.sumologic.com/docs/send-data/hosted-collectors/http-source/
 *
 * Sumo Logic HTTP Sources accept raw POST bodies to a per-source URL.
 * Auth is encoded in the URL itself (no token header). Source category
 * and metadata can be attached via the optional `X-Sumo-*` headers.
 *
 * Wire format: one JSON object per event, newline-delimited body.
 */

import type { AuditSink } from "./memory.js";
import type { AuditEvent } from "../event.js";

export interface SumoLogicOptions {
  /** Full HTTP source URL from Sumo Logic's UI. */
  url: string;
  /** X-Sumo-Name header: human-readable source name. */
  sourceName?: string;
  /** X-Sumo-Category header: ingestion category (controls Kibana-like search scope). */
  sourceCategory?: string;
  /** X-Sumo-Host header. */
  sourceHost?: string;
  /** Additional fields appended to each event payload. */
  fields?: Record<string, string | number>;
  timeoutMs?: number;
  fetch?: typeof fetch;
}

export function sumoLogicPayload(
  event: AuditEvent,
  extraFields: Record<string, string | number> = {},
): Record<string, unknown> {
  return {
    timestamp_ms: Math.floor(event.timestamp * 1000),
    kind: event.kind,
    execution_id: event.executionId,
    schema_version: event.schemaVersion,
    ...event.data,
    ...extraFields,
  };
}

export class SumoLogicSink implements AuditSink {
  readonly url: string;
  readonly headers: Record<string, string>;
  readonly fields: Record<string, string | number>;
  readonly timeoutMs: number;
  private readonly _fetch: typeof fetch;
  private _dropped = 0;

  constructor(opts: SumoLogicOptions) {
    this.url = opts.url;
    this.fields = opts.fields ?? {};
    this.timeoutMs = opts.timeoutMs ?? 10_000;
    this._fetch = opts.fetch ?? fetch;

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (opts.sourceName !== undefined) headers["X-Sumo-Name"] = opts.sourceName;
    if (opts.sourceCategory !== undefined)
      headers["X-Sumo-Category"] = opts.sourceCategory;
    if (opts.sourceHost !== undefined) headers["X-Sumo-Host"] = opts.sourceHost;
    this.headers = headers;
  }

  get droppedCount(): number {
    return this._dropped;
  }

  async emit(event: AuditEvent): Promise<void> {
    const body = JSON.stringify(sumoLogicPayload(event, this.fields));
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      await this._fetch(this.url, {
        method: "POST",
        headers: this.headers,
        body,
        signal: controller.signal,
      });
    } catch {
      this._dropped += 1;
    } finally {
      clearTimeout(timer);
    }
  }
}
