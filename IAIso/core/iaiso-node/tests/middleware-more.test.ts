import { describe, expect, it } from "vitest";

import { MemorySink } from "../src/audit/sinks/memory.js";
import { BoundedExecution } from "../src/core/execution.js";
import {
  CohereBoundedClient,
  MistralBoundedClient,
  createLiteLLMClient,
} from "../src/middleware/index.js";

describe("MistralBoundedClient", () => {
  it("accounts totalTokens and toolCalls", async () => {
    const sink = new MemorySink();
    const exec = BoundedExecution.start({ audit_sink: sink });
    const mock = {
      chat: {
        complete: async () => ({
          model: "mistral-large",
          usage: { promptTokens: 50, completionTokens: 75, totalTokens: 125 },
          choices: [
            {
              message: {
                toolCalls: [{ id: "a", function: { name: "search" } }],
              },
            },
          ],
        }),
      },
    };
    const client = new MistralBoundedClient(mock, exec);
    await client.chat.complete({});
    const step = sink.events.find((e) => e.kind === "engine.step")!;
    expect(step.data["tokens"]).toBe(125);
    expect(step.data["tool_calls"]).toBe(1);
    expect(step.data["tag"]).toBe("mistral.chat.complete:mistral-large");
    exec.close();
  });
});

describe("CohereBoundedClient", () => {
  it("reads tokens from meta.billedUnits", async () => {
    const sink = new MemorySink();
    const exec = BoundedExecution.start({ audit_sink: sink });
    const mock = {
      chat: async () => ({
        model: "command-r",
        meta: {
          billedUnits: { inputTokens: 40, outputTokens: 60 },
        },
        toolCalls: [{ name: "search" }, { name: "fetch" }],
      }),
    };
    const client = new CohereBoundedClient(mock, exec);
    await client.chat({});
    const step = sink.events.find((e) => e.kind === "engine.step")!;
    expect(step.data["tokens"]).toBe(100);
    expect(step.data["tool_calls"]).toBe(2);
    exec.close();
  });

  it("reads tokens from snake_case billed_units too", async () => {
    const sink = new MemorySink();
    const exec = BoundedExecution.start({ audit_sink: sink });
    const mock = {
      chat: async () => ({
        model: "command-r-plus",
        meta: {
          billed_units: { input_tokens: 10, output_tokens: 20 },
        },
      }),
    };
    const client = new CohereBoundedClient(mock, exec);
    await client.chat({});
    const step = sink.events.find((e) => e.kind === "engine.step")!;
    expect(step.data["tokens"]).toBe(30);
    exec.close();
  });
});

describe("createLiteLLMClient", () => {
  it("constructs the provided OpenAI class with the LiteLLM proxy URL", () => {
    class FakeOpenAI {
      constructor(public opts: unknown) {}
    }
    const client = createLiteLLMClient(FakeOpenAI, {
      baseURL: "https://litellm.example.com/v1",
      apiKey: "sk-local-key",
      defaultHeaders: { "X-Tenant": "acme" },
    });
    expect(client).toBeInstanceOf(FakeOpenAI);
    expect((client as FakeOpenAI).opts).toMatchObject({
      baseURL: "https://litellm.example.com/v1",
      apiKey: "sk-local-key",
      defaultHeaders: { "X-Tenant": "acme" },
    });
  });
});
