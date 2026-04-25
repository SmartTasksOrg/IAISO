import { describe, expect, it } from "vitest";

import { AuditEvent } from "../src/audit/event.js";
import {
  DatadogLogsSink,
  LokiSink,
  SplunkHECSink,
  datadogLogsPayload,
  lokiPayload,
  splunkHECPayload,
} from "../src/audit/index.js";

const EVT = new AuditEvent(
  "exec-42",
  "engine.step",
  1700000000.5,
  { step: 1, pressure: 0.12, tag: "search" },
);

describe("splunkHECPayload", () => {
  it("wraps event with HEC envelope", () => {
    const payload = splunkHECPayload(EVT, {
      source: "iaiso",
      sourcetype: "iaiso:audit",
      index: "main",
      host: "worker-01",
    });
    expect(payload).toMatchObject({
      time: 1700000000.5,
      source: "iaiso",
      sourcetype: "iaiso:audit",
      index: "main",
      host: "worker-01",
    });
    const eventObj = payload.event as Record<string, unknown>;
    expect(eventObj.kind).toBe("engine.step");
    expect(eventObj.execution_id).toBe("exec-42");
    expect(eventObj.schema_version).toBe("1.0");
    expect(eventObj.pressure).toBe(0.12);
  });

  it("omits optional fields when not provided", () => {
    const payload = splunkHECPayload(EVT, {});
    expect(payload).not.toHaveProperty("index");
    expect(payload).not.toHaveProperty("host");
  });
});

describe("SplunkHECSink (mocked fetch)", () => {
  it("posts to the HEC URL with Splunk auth header", async () => {
    const calls: Array<{ url: string; init: RequestInit | undefined }> = [];
    const mockFetch = async (url: string | URL | Request, init?: RequestInit) => {
      calls.push({ url: String(url), init });
      return new Response("{}", { status: 200 });
    };
    const sink = new SplunkHECSink({
      url: "https://splunk.example.com:8088/services/collector/event",
      token: "abc-123-token",
      fetch: mockFetch as unknown as typeof fetch,
    });
    await sink.emit(EVT);
    expect(calls).toHaveLength(1);
    const call = calls[0]!;
    expect(call.url).toBe("https://splunk.example.com:8088/services/collector/event");
    const headers = call.init!.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Splunk abc-123-token");
  });
});

describe("datadogLogsPayload", () => {
  it("serializes event as message JSON with tags", () => {
    const payload = datadogLogsPayload(EVT, {
      service: "iaiso",
      ddsource: "iaiso",
      ddtags: "env:prod,team:ai",
      hostname: "worker-01",
    });
    expect(payload.ddsource).toBe("iaiso");
    expect(payload.service).toBe("iaiso");
    expect(payload.ddtags).toBe("env:prod,team:ai");
    expect(payload.hostname).toBe("worker-01");
    const msg = JSON.parse(payload.message as string);
    expect(msg.kind).toBe("engine.step");
    expect(msg.schema_version).toBe("1.0");
  });
});

describe("DatadogLogsSink (mocked fetch)", () => {
  it("posts to the Logs URL with DD-API-KEY header", async () => {
    const calls: Array<{ url: string; init: RequestInit | undefined }> = [];
    const mockFetch = async (url: string | URL | Request, init?: RequestInit) => {
      calls.push({ url: String(url), init });
      return new Response("{}", { status: 200 });
    };
    const sink = new DatadogLogsSink({
      url: "https://http-intake.logs.datadoghq.com/api/v2/logs",
      apiKey: "dd-api-key-xyz",
      fetch: mockFetch as unknown as typeof fetch,
    });
    await sink.emit(EVT);
    expect(calls).toHaveLength(1);
    const headers = calls[0]!.init!.headers as Record<string, string>;
    expect(headers["DD-API-KEY"]).toBe("dd-api-key-xyz");
    const body = JSON.parse(calls[0]!.init!.body as string);
    expect(Array.isArray(body)).toBe(true);
    expect(body[0].ddsource).toBe("iaiso");
  });
});

describe("lokiPayload", () => {
  it("builds a streams/values entry with ns timestamp", () => {
    const payload = lokiPayload(EVT, { job: "iaiso", env: "prod" });
    const streams = payload.streams as Array<{
      stream: Record<string, string>;
      values: string[][];
    }>;
    expect(streams).toHaveLength(1);
    expect(streams[0]!.stream).toEqual({ job: "iaiso", env: "prod" });
    const [ns, line] = streams[0]!.values[0]!;
    expect(ns).toBe(String(Math.floor(1700000000.5 * 1e9)));
    expect(line).toContain('"kind":"engine.step"');
  });
});

describe("LokiSink (mocked fetch)", () => {
  it("adds basic auth when username+password supplied", async () => {
    const calls: Array<{ init: RequestInit | undefined }> = [];
    const mockFetch = async (_url: string | URL | Request, init?: RequestInit) => {
      calls.push({ init });
      return new Response("{}", { status: 204 });
    };
    const sink = new LokiSink({
      url: "https://logs.example.com/loki/api/v1/push",
      username: "me",
      password: "secret",
      fetch: mockFetch as unknown as typeof fetch,
    });
    await sink.emit(EVT);
    const headers = calls[0]!.init!.headers as Record<string, string>;
    // "me:secret" base64 = "bWU6c2VjcmV0"
    expect(headers.Authorization).toBe("Basic bWU6c2VjcmV0");
  });
});
