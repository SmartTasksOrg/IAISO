import { describe, expect, it } from "vitest";

import { AuditEvent } from "../src/audit/event.js";
import {
  ElasticECSSink,
  NewRelicLogsSink,
  SumoLogicSink,
  elasticECSPayload,
  newRelicLogsPayload,
  sumoLogicPayload,
} from "../src/audit/index.js";

const EVT = new AuditEvent("exec-9", "engine.step", 1700000000.25, {
  step: 3,
  pressure: 0.42,
});

describe("elasticECSPayload", () => {
  it("maps IAIso event to ECS-compliant fields", () => {
    const payload = elasticECSPayload(EVT, {
      dataset: "iaiso.audit",
      labels: { env: "prod" },
    });
    expect(payload["@timestamp"]).toBe(new Date(1700000000250).toISOString());
    const evBlock = payload.event as Record<string, unknown>;
    expect(evBlock.kind).toBe("event");
    expect(evBlock.dataset).toBe("iaiso.audit");
    expect(evBlock.action).toBe("engine.step");
    expect(evBlock.id).toBe("exec-9");
    const labels = payload.labels as Record<string, unknown>;
    expect(labels.execution_id).toBe("exec-9");
    expect(labels.env).toBe("prod");
  });
});

describe("ElasticECSSink (mocked fetch)", () => {
  it("sets Basic auth when username+password supplied", async () => {
    const calls: Array<{ init: RequestInit | undefined }> = [];
    const mockFetch = async (_: string | URL | Request, init?: RequestInit) => {
      calls.push({ init });
      return new Response("{}", { status: 200 });
    };
    const sink = new ElasticECSSink({
      url: "https://es.example.com/iaiso/_doc",
      username: "elastic",
      password: "changeme",
      fetch: mockFetch as unknown as typeof fetch,
    });
    await sink.emit(EVT);
    const headers = calls[0]!.init!.headers as Record<string, string>;
    // "elastic:changeme" base64 = "ZWxhc3RpYzpjaGFuZ2VtZQ=="
    expect(headers.Authorization).toBe("Basic ZWxhc3RpYzpjaGFuZ2VtZQ==");
  });

  it("sets ApiKey auth when apiKey supplied", async () => {
    const calls: Array<{ init: RequestInit | undefined }> = [];
    const mockFetch = async (_: string | URL | Request, init?: RequestInit) => {
      calls.push({ init });
      return new Response("{}", { status: 200 });
    };
    const sink = new ElasticECSSink({
      url: "https://es.example.com/iaiso/_doc",
      apiKey: "abc123",
      fetch: mockFetch as unknown as typeof fetch,
    });
    await sink.emit(EVT);
    const headers = calls[0]!.init!.headers as Record<string, string>;
    expect(headers.Authorization).toBe("ApiKey abc123");
  });
});

describe("sumoLogicPayload", () => {
  it("flattens event.data onto the payload with timestamp_ms", () => {
    const payload = sumoLogicPayload(EVT, { env: "prod" });
    expect(payload.timestamp_ms).toBe(1700000000250);
    expect(payload.kind).toBe("engine.step");
    expect(payload.execution_id).toBe("exec-9");
    expect(payload.pressure).toBe(0.42);
    expect(payload.env).toBe("prod");
  });
});

describe("SumoLogicSink (mocked fetch)", () => {
  it("sets X-Sumo-* headers from options", async () => {
    const calls: Array<{ init: RequestInit | undefined }> = [];
    const mockFetch = async (_: string | URL | Request, init?: RequestInit) => {
      calls.push({ init });
      return new Response("{}", { status: 200 });
    };
    const sink = new SumoLogicSink({
      url: "https://collectors.sumologic.com/receiver/...",
      sourceName: "iaiso-prod",
      sourceCategory: "iaiso/audit",
      sourceHost: "worker-01",
      fetch: mockFetch as unknown as typeof fetch,
    });
    await sink.emit(EVT);
    const headers = calls[0]!.init!.headers as Record<string, string>;
    expect(headers["X-Sumo-Name"]).toBe("iaiso-prod");
    expect(headers["X-Sumo-Category"]).toBe("iaiso/audit");
    expect(headers["X-Sumo-Host"]).toBe("worker-01");
  });
});

describe("newRelicLogsPayload", () => {
  it("builds a log record with iaiso.* prefixed attributes", () => {
    const payload = newRelicLogsPayload(EVT, {
      service: "iaiso",
      hostname: "worker-01",
      attributes: { "team": "platform" },
    });
    expect(payload.timestamp).toBe(1700000000250);
    expect(payload.message).toBe("engine.step");
    const attrs = payload.attributes as Record<string, unknown>;
    expect(attrs.logtype).toBe("iaiso");
    expect(attrs["iaiso.kind"]).toBe("engine.step");
    expect(attrs["iaiso.execution_id"]).toBe("exec-9");
    expect(attrs["iaiso.pressure"]).toBe(0.42);
    expect(attrs["host.name"]).toBe("worker-01");
    expect(attrs.team).toBe("platform");
  });
});

describe("NewRelicLogsSink (mocked fetch)", () => {
  it("sends a JSON array with Api-Key header", async () => {
    const calls: Array<{ init: RequestInit | undefined; url: string }> = [];
    const mockFetch = async (url: string | URL | Request, init?: RequestInit) => {
      calls.push({ url: String(url), init });
      return new Response("{}", { status: 202 });
    };
    const sink = new NewRelicLogsSink({
      apiKey: "NRAK-KEY",
      service: "iaiso",
      fetch: mockFetch as unknown as typeof fetch,
    });
    await sink.emit(EVT);
    expect(calls[0]!.url).toBe("https://log-api.newrelic.com/log/v1");
    const headers = calls[0]!.init!.headers as Record<string, string>;
    expect(headers["Api-Key"]).toBe("NRAK-KEY");
    const body = JSON.parse(calls[0]!.init!.body as string);
    expect(Array.isArray(body)).toBe(true);
    expect(body[0].attributes.logtype).toBe("iaiso");
  });
});
