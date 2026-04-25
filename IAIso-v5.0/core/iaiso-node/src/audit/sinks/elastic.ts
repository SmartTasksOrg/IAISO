/**
 * Elastic Common Schema (ECS) sink.
 *
 * ECS docs:
 *   https://www.elastic.co/guide/en/ecs/current/ecs-reference.html
 *
 * The IAIso audit event is mapped to ECS-compliant field names so it
 * ingests cleanly into Elastic Stack (Elasticsearch + Kibana). Payload
 * targets the Elasticsearch bulk API or a generic Elastic ingest
 * endpoint. Each emit POSTs one event; batch upstream with a log
 * shipper (Logstash, Fluent Bit) for high volume.
 *
 * Field mapping:
 *   - @timestamp:         ISO-8601 from event.timestamp (seconds→ms)
 *   - event.kind:         "event"
 *   - event.dataset:      "iaiso.audit"
 *   - event.action:       event.kind
 *   - event.id:           event.execution_id
 *   - event.code:         schema version
 *   - labels.execution_id
 *   - labels.*:           flattened event.data
 */

import type { AuditSink } from "./memory.js";
import type { AuditEvent } from "../event.js";

export interface ElasticECSOptions {
  /** Full bulk or document URL. Supports:
   *  - POST /<index>/_doc (single doc)
   *  - POST /_bulk (batch NDJSON)
   *  This sink uses the single-doc shape for simplicity. */
  url: string;
  /** Elasticsearch API key (`ApiKey <base64>` header). Mutually exclusive with username/password. */
  apiKey?: string;
  /** Basic-auth username (e.g. `elastic`). */
  username?: string;
  /** Basic-auth password. */
  password?: string;
  /** Dataset label (ECS `event.dataset`). Default "iaiso.audit". */
  dataset?: string;
  /** Additional labels merged into every document. */
  labels?: Record<string, string>;
  timeoutMs?: number;
  fetch?: typeof fetch;
}

export function elasticECSPayload(
  event: AuditEvent,
  opts: Pick<ElasticECSOptions, "dataset" | "labels">,
): Record<string, unknown> {
  const isoTs = new Date(event.timestamp * 1000).toISOString();
  return {
    "@timestamp": isoTs,
    event: {
      kind: "event",
      dataset: opts.dataset ?? "iaiso.audit",
      action: event.kind,
      id: event.executionId,
      code: event.schemaVersion,
    },
    labels: {
      execution_id: event.executionId,
      ...(opts.labels ?? {}),
    },
    iaiso: {
      ...event.data,
    },
    message: event.kind,
  };
}

export class ElasticECSSink implements AuditSink {
  readonly url: string;
  readonly headers: Record<string, string>;
  readonly payloadOpts: Pick<ElasticECSOptions, "dataset" | "labels">;
  readonly timeoutMs: number;
  private readonly _fetch: typeof fetch;
  private _dropped = 0;

  constructor(opts: ElasticECSOptions) {
    this.url = opts.url;
    this.timeoutMs = opts.timeoutMs ?? 10_000;
    this._fetch = opts.fetch ?? fetch;
    this.payloadOpts = { dataset: opts.dataset, labels: opts.labels };

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (opts.apiKey) {
      headers.Authorization = `ApiKey ${opts.apiKey}`;
    } else if (opts.username !== undefined && opts.password !== undefined) {
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
    const body = JSON.stringify(elasticECSPayload(event, this.payloadOpts));
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
