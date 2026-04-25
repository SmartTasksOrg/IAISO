/**
 * Datadog Logs sink.
 *
 * Datadog Logs intake docs:
 *   https://docs.datadoghq.com/api/latest/logs/
 *
 * Wire format: JSON array of log entries. Auth via `DD-API-KEY` header.
 * Tags go on each entry via `ddtags`. Hostname via `hostname`. The
 * IAIso event is inlined as the message body.
 */

import type { AuditSink } from "./memory.js";
import type { AuditEvent } from "../event.js";

export interface DatadogLogsOptions {
  /** Full URL, e.g. https://http-intake.logs.datadoghq.com/api/v2/logs */
  url: string;
  apiKey: string;
  service?: string;
  ddsource?: string;
  ddtags?: string;
  hostname?: string;
  timeoutMs?: number;
  fetch?: typeof fetch;
}

export function datadogLogsPayload(
  event: AuditEvent,
  opts: Omit<DatadogLogsOptions, "url" | "apiKey" | "timeoutMs" | "fetch">,
): Record<string, unknown> {
  const entry: Record<string, unknown> = {
    message: JSON.stringify({
      kind: event.kind,
      execution_id: event.executionId,
      schema_version: event.schemaVersion,
      timestamp: event.timestamp,
      ...event.data,
    }),
    ddsource: opts.ddsource ?? "iaiso",
    service: opts.service ?? "iaiso",
  };
  if (opts.ddtags !== undefined) entry.ddtags = opts.ddtags;
  if (opts.hostname !== undefined) entry.hostname = opts.hostname;
  return entry;
}

export class DatadogLogsSink implements AuditSink {
  readonly url: string;
  readonly apiKey: string;
  readonly payloadOpts: Omit<
    DatadogLogsOptions,
    "url" | "apiKey" | "timeoutMs" | "fetch"
  >;
  readonly timeoutMs: number;
  private readonly _fetch: typeof fetch;
  private _dropped = 0;

  constructor(opts: DatadogLogsOptions) {
    this.url = opts.url;
    this.apiKey = opts.apiKey;
    this.timeoutMs = opts.timeoutMs ?? 10_000;
    this._fetch = opts.fetch ?? fetch;
    this.payloadOpts = {
      service: opts.service,
      ddsource: opts.ddsource,
      ddtags: opts.ddtags,
      hostname: opts.hostname,
    };
  }

  get droppedCount(): number {
    return this._dropped;
  }

  async emit(event: AuditEvent): Promise<void> {
    const body = JSON.stringify([datadogLogsPayload(event, this.payloadOpts)]);
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      await this._fetch(this.url, {
        method: "POST",
        headers: {
          "DD-API-KEY": this.apiKey,
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
