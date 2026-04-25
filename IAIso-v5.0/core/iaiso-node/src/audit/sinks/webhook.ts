/**
 * Webhook sink — POSTs events to an HTTP endpoint.
 *
 * Uses an async bounded queue. Drops events under sustained backpressure
 * rather than blocking the agent (mirrors the Python default).
 * Drop count is available via `droppedCount` for metrics/alerting.
 */

import type { AuditSink } from "./memory.js";
import type { AuditEvent } from "../event.js";

export interface WebhookSinkOptions {
  url: string;
  headers?: Record<string, string>;
  queueMax?: number;
  timeoutMs?: number;
  /** Custom fetch implementation (for tests). Defaults to globalThis.fetch. */
  fetch?: typeof fetch;
}

export class WebhookSink implements AuditSink {
  readonly url: string;
  readonly headers: Record<string, string>;
  readonly queueMax: number;
  readonly timeoutMs: number;
  private readonly _fetch: typeof fetch;
  private readonly _queue: AuditEvent[] = [];
  private _pump: Promise<void> | null = null;
  private _closed = false;
  private _dropped = 0;

  constructor(opts: WebhookSinkOptions) {
    this.url = opts.url;
    this.headers = { "Content-Type": "application/json", ...(opts.headers ?? {}) };
    this.queueMax = opts.queueMax ?? 1024;
    this.timeoutMs = opts.timeoutMs ?? 5000;
    this._fetch = opts.fetch ?? fetch;
  }

  get droppedCount(): number {
    return this._dropped;
  }

  emit(event: AuditEvent): void {
    if (this._closed) return;
    if (this._queue.length >= this.queueMax) {
      this._dropped += 1;
      return;
    }
    this._queue.push(event);
    if (!this._pump) {
      this._pump = this._drain();
    }
  }

  private async _drain(): Promise<void> {
    try {
      while (this._queue.length > 0) {
        const event = this._queue.shift()!;
        await this._post(event);
      }
    } finally {
      this._pump = null;
    }
  }

  private async _post(event: AuditEvent): Promise<void> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      await this._fetch(this.url, {
        method: "POST",
        headers: this.headers,
        body: event.toJsonString(),
        signal: controller.signal,
      });
    } catch {
      // Best-effort delivery: increment a drop counter; don't throw into the agent loop.
      this._dropped += 1;
    } finally {
      clearTimeout(timer);
    }
  }

  async close(): Promise<void> {
    this._closed = true;
    if (this._pump) {
      await this._pump;
    }
  }
}
