/**
 * LangChain callback handler — hooks pressure accounting into a
 * LangChain runnable/chain via the `@langchain/core` callback API.
 *
 * Install:
 *   npm install @langchain/core
 *
 * Example:
 *   import { ChatAnthropic } from "@langchain/anthropic";
 *   import { BoundedExecution, IaisoCallbackHandler } from "@iaiso/core";
 *
 *   await BoundedExecution.run({ config, audit_sink }, async (exec) => {
 *     const handler = new IaisoCallbackHandler(exec);
 *     const model = new ChatAnthropic({ model: "claude-opus-4-7" });
 *     const response = await model.invoke(prompt, { callbacks: [handler] });
 *   });
 *
 * Tokens come from `llmOutput.tokenUsage` where available (Anthropic,
 * OpenAI). Tool-call accounting happens via `handleToolStart`.
 */

import { BoundedExecution } from "../core/execution.js";

interface TokenUsage {
  totalTokens?: number;
  promptTokens?: number;
  completionTokens?: number;
  inputTokens?: number;
  outputTokens?: number;
}

interface LLMResult {
  llmOutput?: {
    tokenUsage?: TokenUsage;
    usage?: TokenUsage;
  };
  generations?: Array<Array<{ text?: string; message?: unknown }>>;
}

/**
 * IAIso callback handler. Implements a minimal subset of the
 * `@langchain/core/callbacks` `BaseCallbackHandler` interface — just the
 * hooks we need (LLM-end + tool-start). Typed structurally so we don't
 * have to take `@langchain/core` as a hard import.
 */
export class IaisoCallbackHandler {
  readonly name = "iaiso_callback_handler";
  readonly _execution: BoundedExecution;
  readonly awaitHandlers = true;
  readonly ignoreLLM = false;
  readonly ignoreChain = false;
  readonly ignoreAgent = false;
  readonly ignoreRetriever = false;
  readonly ignoreCustomEvent = false;

  constructor(execution: BoundedExecution) {
    this._execution = execution;
  }

  async handleLLMEnd(output: LLMResult): Promise<void> {
    const usage = output.llmOutput?.tokenUsage ?? output.llmOutput?.usage ?? {};
    const tokens =
      Number(usage.totalTokens ?? 0) ||
      Number(usage.promptTokens ?? 0) + Number(usage.completionTokens ?? 0) ||
      Number(usage.inputTokens ?? 0) + Number(usage.outputTokens ?? 0);

    if (tokens > 0) {
      this._execution.recordTokens(tokens, "langchain.llm_end");
    }
  }

  async handleToolStart(
    tool: { name?: string; id?: string[] } | unknown,
  ): Promise<void> {
    const toolName =
      typeof tool === "object" && tool !== null && "name" in tool
        ? String((tool as { name?: string }).name ?? "unknown")
        : "unknown";
    this._execution.recordToolCall({ name: `langchain:${toolName}` });
  }

  async handleChainError(): Promise<void> {
    // no-op: don't double-account errors; the engine's state is fine
  }
}
