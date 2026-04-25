/**
 * New Relic Logs sink.
 *
 * New Relic Logs API docs:
 *   https://docs.newrelic.com/docs/logs/log-api/introduction-log-api/
 *
 * Endpoint (US region):
 *   https://log-api.newrelic.com/log/v1
 * Endpoint (EU region):
 *   https://log-api.eu.newrelic.com/log/v1
 *
 * Wire format: JSON array of log entries, each with `timestamp` (ms),
 * `message`, and arbitrary attributes. Auth via `Api-Key` header.
 */

import type { AuditSink } from "./memory.js";
import type { AuditEvent } from "../event.js";

export interface NewRelicLogsOptions {
  /** Full logs endpoint URL. Default: US-region logs endpoint. */
  url?: string;
  /** New Relic license key (not the user API key). */
  apiKey: string;
  /** Service name / logtype, embedded as an attribute. */
  service?: string;
  /** Hostname attribute. */
  hostname?: string;
  /** Additional attributes merged into every log entry. */
  attributes?: Record<string, string | number>;
  timeoutMs?: number;
  fetch?: typeof fetch;
}

export function newRelicLogsPayload(
  event: AuditEvent,
  opts: Pick<NewRelicLogsOptions, "service" | "hostname" | "attributes">,
): Record<string, unknown> {
  const attrs: Record<string, unknown> = {
    logtype: opts.service ?? "iaiso",
    "iaiso.kind": event.kind,
    "iaiso.execution_id": event.executionId,
    "iaiso.schema_version": event.schemaVersion,
    ...(opts.attributes ?? {}),
  };
  if (opts.hostname !== undefined) attrs["host.name"] = opts.hostname;
  // Also surface event payload as flat attributes with an `iaiso.` prefix.
  for (const [k, v] of Object.entries(event.data)) {
    attrs[`iaiso.${k}`] = v as never;
  }

  return {
    timestamp: Math.floor(event.timestamp * 1000),
    message: event.kind,
    attributes: attrs,
  };
}

export class NewRelicLogsSink implements AuditSink {
  readonly url: string;
  readonly headers: Record<string, string>;
  readonly payloadOpts: Pick<
    NewRelicLogsOptions,
    "service" | "hostname" | "attributes"
  >;
  readonly timeoutMs: number;
  private readonly _fetch: typeof fetch;
  private _dropped = 0;

  constructor(opts: NewRelicLogsOptions) {
    this.url = opts.url ?? "https://log-api.newrelic.com/log/v1";
    this.timeoutMs = opts.timeoutMs ?? 10_000;
    this._fetch = opts.fetch ?? fetch;
    this.payloadOpts = {
      service: opts.service,
      hostname: opts.hostname,
      attributes: opts.attributes,
    };
    this.headers = {
      "Content-Type": "application/json",
      "Api-Key": opts.apiKey,
    };
  }

  get droppedCount(): number {
    return this._dropped;
  }

  async emit(event: AuditEvent): Promise<void> {
    const body = JSON.stringify([
      newRelicLogsPayload(event, this.payloadOpts),
    ]);
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
