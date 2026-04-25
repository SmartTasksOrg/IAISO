/**
 * Splunk HTTP Event Collector (HEC) sink.
 *
 * Splunk HEC docs:
 *   https://docs.splunk.com/Documentation/Splunk/latest/Data/FormateventsforHTTPEventCollector
 *
 * Wire format: one JSON object per event, concatenated by newlines
 * (NOT a JSON array). Auth via `Authorization: Splunk <token>`.
 */

import type { AuditSink } from "./memory.js";
import type { AuditEvent } from "../event.js";

export interface SplunkHECOptions {
  url: string;
  token: string;
  index?: string;
  source?: string;
  sourcetype?: string;
  host?: string;
  timeoutMs?: number;
  fetch?: typeof fetch;
}

export function splunkHECPayload(
  event: AuditEvent,
  opts: Omit<SplunkHECOptions, "url" | "token" | "timeoutMs" | "fetch">,
): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    time: event.timestamp,
    source: opts.source ?? "iaiso",
    sourcetype: opts.sourcetype ?? "iaiso:audit",
    event: {
      kind: event.kind,
      execution_id: event.executionId,
      schema_version: event.schemaVersion,
      ...event.data,
    },
  };
  if (opts.index !== undefined) payload.index = opts.index;
  if (opts.host !== undefined) payload.host = opts.host;
  return payload;
}

/**
 * Splunk HEC sink. Events are posted individually (one request per
 * event) for simplicity; for high-volume fleets, batch upstream via a
 * log shipper (Fluent Bit, Vector) writing to a `JsonlFileSink`.
 */
export class SplunkHECSink implements AuditSink {
  readonly url: string;
  readonly token: string;
  readonly payloadOpts: Omit<
    SplunkHECOptions,
    "url" | "token" | "timeoutMs" | "fetch"
  >;
  readonly timeoutMs: number;
  private readonly _fetch: typeof fetch;
  private _dropped = 0;

  constructor(opts: SplunkHECOptions) {
    this.url = opts.url;
    this.token = opts.token;
    this.timeoutMs = opts.timeoutMs ?? 10_000;
    this._fetch = opts.fetch ?? fetch;
    this.payloadOpts = {
      index: opts.index,
      source: opts.source,
      sourcetype: opts.sourcetype,
      host: opts.host,
    };
  }

  get droppedCount(): number {
    return this._dropped;
  }

  async emit(event: AuditEvent): Promise<void> {
    const body = JSON.stringify(splunkHECPayload(event, this.payloadOpts));
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      await this._fetch(this.url, {
        method: "POST",
        headers: {
          Authorization: `Splunk ${this.token}`,
          "Content-Type": "application/json",
        },
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
