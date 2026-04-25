/**
 * Grafana Loki sink.
 *
 * Loki push API docs:
 *   https://grafana.com/docs/loki/latest/reference/loki-http-api/#push-log-entries-to-loki
 *
 * Wire format:
 *   {
 *     "streams": [
 *       {
 *         "stream": { "job": "iaiso", ... },
 *         "values": [["<nanosecond timestamp>", "<line>"], ...]
 *       }
 *     ]
 *   }
 *
 * Timestamps are strings of nanoseconds since epoch.
 */

import type { AuditSink } from "./memory.js";
import type { AuditEvent } from "../event.js";

export interface LokiOptions {
  /** Full push URL, e.g. https://logs-prod3.grafana.net/loki/api/v1/push */
  url: string;
  /** Labels attached to every stream. Default: { job: "iaiso" }. */
  labels?: Record<string, string>;
  /** Basic-auth user (optional). */
  username?: string;
  /** Basic-auth password / API key (optional). */
  password?: string;
  /** Custom header name -> value pairs. */
  headers?: Record<string, string>;
  timeoutMs?: number;
  fetch?: typeof fetch;
}

export function lokiPayload(
  event: AuditEvent,
  labels: Record<string, string>,
): Record<string, unknown> {
  // Loki requires nanosecond-precision timestamps as strings
  const ns = String(Math.floor(event.timestamp * 1e9));
  const line = JSON.stringify({
    kind: event.kind,
    execution_id: event.executionId,
    schema_version: event.schemaVersion,
    ...event.data,
  });
  return {
    streams: [
      {
        stream: labels,
        values: [[ns, line]],
      },
    ],
  };
}

export class LokiSink implements AuditSink {
  readonly url: string;
  readonly labels: Record<string, string>;
  readonly headers: Record<string, string>;
  readonly timeoutMs: number;
  private readonly _fetch: typeof fetch;
  private _dropped = 0;

  constructor(opts: LokiOptions) {
    this.url = opts.url;
    this.labels = opts.labels ?? { job: "iaiso" };
    this.timeoutMs = opts.timeoutMs ?? 10_000;
    this._fetch = opts.fetch ?? fetch;

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(opts.headers ?? {}),
    };
    if (opts.username !== undefined && opts.password !== undefined) {
      const creds = Buffer.from(
        `${opts.username}:${opts.password}`,
        "utf8",
      ).toString("base64");
      headers.Authorization = `Basic ${creds}`;
    }
    this.headers = headers;
  }

  get droppedCount(): number {
    return this._dropped;
  }

  async emit(event: AuditEvent): Promise<void> {
    const body = JSON.stringify(lokiPayload(event, this.labels));
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
