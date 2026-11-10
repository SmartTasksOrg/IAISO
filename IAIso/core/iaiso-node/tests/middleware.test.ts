import { describe, expect, it } from "vitest";

import { MemorySink } from "../src/audit/sinks/memory.js";
import { BoundedExecution, ExecutionLocked } from "../src/core/execution.js";
import { PressureConfig } from "../src/core/engine.js";
import {
  AnthropicBoundedClient,
  EscalationRaised,
  OpenAIBoundedClient,
  IaisoCallbackHandler,
} from "../src/middleware/index.js";

describe("AnthropicBoundedClient", () => {
  it("accounts for usage tokens and tool_use blocks", async () => {
    const sink = new MemorySink();
    const exec = BoundedExecution.start({ audit_sink: sink });
    const mock = {
      messages: {
        create: async (_: Record<string, unknown>) => ({
          model: "claude-opus-4-7",
          usage: { input_tokens: 100, output_tokens: 250 },
          content: [
            { type: "text", text: "hi" },
            { type: "tool_use", id: "1", name: "search", input: {} },
            { type: "tool_use", id: "2", name: "fetch", input: {} },
          ],
        }),
      },
    };
    const client = new AnthropicBoundedClient(mock, exec);
    await client.messages.create({ model: "claude-opus-4-7", max_tokens: 1024, messages: [] });
    const stepEvents = sink.events.filter((e) => e.kind === "engine.step");
    expect(stepEvents).toHaveLength(1);
    expect(stepEvents[0]!.data["tokens"]).toBe(350);
    expect(stepEvents[0]!.data["tool_calls"]).toBe(2);
    expect(stepEvents[0]!.data["tag"]).toBe("anthropic.messages.create:claude-opus-4-7");
    exec.close();
  });

  it("throws ExecutionLocked when the execution is locked", async () => {
    const sink = new MemorySink();
    const exec = BoundedExecution.start({
      audit_sink: sink,
      config: new PressureConfig({
        escalation_threshold: 0.5,
        release_threshold: 0.75,
        dissipation_per_step: 0.0,
        depth_coefficient: 0.75,
      }),
    });
    exec.recordStep({ depth: 1 }); // release + lock
    const mock = {
      messages: {
        create: async () => ({ model: "m", usage: { input_tokens: 0, output_tokens: 0 }, content: [] }),
      },
    };
    const client = new AnthropicBoundedClient(mock, exec);
    await expect(client.messages.create({})).rejects.toThrow(ExecutionLocked);
    exec.close();
  });

  it("throws EscalationRaised when flag set + escalated", async () => {
    const sink = new MemorySink();
    const exec = BoundedExecution.start({
      audit_sink: sink,
      config: new PressureConfig({
        escalation_threshold: 0.5,
        release_threshold: 0.9,
        dissipation_per_step: 0.0,
        depth_coefficient: 0.5,
      }),
    });
    exec.recordStep({ depth: 1 }); // escalates, not releases
    const mock = {
      messages: {
        create: async () => ({ model: "m", content: [] }),
      },
    };
    const client = new AnthropicBoundedClient(mock, exec, { raiseOnEscalation: true });
    await expect(client.messages.create({})).rejects.toThrow(EscalationRaised);
    exec.close();
  });
});

describe("OpenAIBoundedClient", () => {
  it("accounts for total_tokens and tool_calls", async () => {
    const sink = new MemorySink();
    const exec = BoundedExecution.start({ audit_sink: sink });
    const mock = {
      chat: {
        completions: {
          create: async () => ({
            model: "gpt-4",
            usage: { prompt_tokens: 80, completion_tokens: 120, total_tokens: 200 },
            choices: [
              {
                message: {
                  tool_calls: [
                    { id: "a", type: "function", function: { name: "x", arguments: "{}" } },
                  ],
                },
              },
            ],
          }),
        },
      },
    };
    const client = new OpenAIBoundedClient(mock, exec);
    await client.chat.completions.create({ model: "gpt-4", messages: [] });
    const stepEvents = sink.events.filter((e) => e.kind === "engine.step");
    expect(stepEvents[0]!.data["tokens"]).toBe(200);
    expect(stepEvents[0]!.data["tool_calls"]).toBe(1);
    exec.close();
  });

  it("falls back to prompt+completion when total_tokens missing", async () => {
    const sink = new MemorySink();
    const exec = BoundedExecution.start({ audit_sink: sink });
    const mock = {
      chat: {
        completions: {
          create: async () => ({
            model: "gpt-4",
            usage: { prompt_tokens: 50, completion_tokens: 75 },
            choices: [{ message: {} }],
          }),
        },
      },
    };
    const client = new OpenAIBoundedClient(mock, exec);
    await client.chat.completions.create({});
    const stepEvents = sink.events.filter((e) => e.kind === "engine.step");
    expect(stepEvents[0]!.data["tokens"]).toBe(125);
    exec.close();
  });
});

describe("IaisoCallbackHandler", () => {
  it("records tokens from handleLLMEnd", async () => {
    const sink = new MemorySink();
    const exec = BoundedExecution.start({ audit_sink: sink });
    const handler = new IaisoCallbackHandler(exec);
    await handler.handleLLMEnd({
      llmOutput: { tokenUsage: { totalTokens: 500 } },
      generations: [[{ text: "hello" }]],
    });
    const stepEvents = sink.events.filter((e) => e.kind === "engine.step");
    expect(stepEvents[0]!.data["tokens"]).toBe(500);
    exec.close();
  });

  it("records tool calls from handleToolStart", async () => {
    const sink = new MemorySink();
    const exec = BoundedExecution.start({ audit_sink: sink });
    const handler = new IaisoCallbackHandler(exec);
    await handler.handleToolStart({ name: "search_web" });
    const stepEvents = sink.events.filter((e) => e.kind === "engine.step");
    expect(stepEvents[0]!.data["tool_calls"]).toBe(1);
    expect(stepEvents[0]!.data["tag"]).toBe("langchain:search_web");
    exec.close();
  });
});
