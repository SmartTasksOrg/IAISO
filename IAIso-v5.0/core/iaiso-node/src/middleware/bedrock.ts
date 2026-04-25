/**
 * AWS Bedrock middleware.
 *
 * Wraps `@aws-sdk/client-bedrock-runtime`. Supports both the Converse
 * API (preferred, provider-agnostic) and the legacy `invokeModel`
 * surface. Token counts come from `response.usage` on Converse and
 * from model-specific fields on `invokeModel` (Anthropic Claude,
 * Amazon Titan, Meta Llama, Cohere all expose usage in the body).
 *
 * Install:
 *   npm install @aws-sdk/client-bedrock-runtime
 *
 * Example (Converse):
 *   import { BedrockRuntimeClient, ConverseCommand } from "@aws-sdk/client-bedrock-runtime";
 *   import { BoundedExecution, BedrockBoundedClient } from "@iaiso/core";
 *
 *   const raw = new BedrockRuntimeClient({ region: "us-east-1" });
 *   await BoundedExecution.run({ config, audit_sink }, async (exec) => {
 *     const client = new BedrockBoundedClient(raw, exec);
 *     const cmd = new ConverseCommand({
 *       modelId: "anthropic.claude-3-5-sonnet-20241022-v2:0",
 *       messages: [{ role: "user", content: [{ text: "hello" }] }],
 *     });
 *     const response = await client.send(cmd);
 *   });
 */

import { BoundedExecution, ExecutionLocked } from "../core/execution.js";
import { StepOutcome } from "../core/types.js";
import { EscalationRaised } from "./anthropic.js";

interface BedrockConverseResponse {
  usage?: {
    inputTokens?: number;
    outputTokens?: number;
    totalTokens?: number;
  };
  output?: {
    message?: {
      content?: Array<{ toolUse?: unknown; text?: string }>;
    };
  };
  stopReason?: string;
  $metadata?: unknown;
}

interface BedrockInvokeResponse {
  body?: Uint8Array | string;
  contentType?: string;
  $metadata?: unknown;
}

interface BedrockCommandLike {
  input?: { modelId?: string };
  constructor: { name: string };
}

interface BedrockClientLike {
  send: (
    command: BedrockCommandLike,
  ) => Promise<BedrockConverseResponse | BedrockInvokeResponse>;
}

export interface BedrockBoundedClientOptions {
  raiseOnEscalation?: boolean;
}

export class BedrockBoundedClient<T extends BedrockClientLike = BedrockClientLike> {
  readonly raw: T;
  private readonly _execution: BoundedExecution;
  private readonly _raiseOnEscalation: boolean;

  constructor(
    client: T,
    execution: BoundedExecution,
    opts: BedrockBoundedClientOptions = {},
  ) {
    this.raw = client;
    this._execution = execution;
    this._raiseOnEscalation = opts.raiseOnEscalation ?? false;
  }

  async send(
    command: BedrockCommandLike,
  ): Promise<BedrockConverseResponse | BedrockInvokeResponse> {
    const pre = this._execution.check();
    if (pre === StepOutcome.Locked) {
      throw new ExecutionLocked(
        `execution ${this._execution.engine.execution_id} is locked`,
      );
    }
    if (pre === StepOutcome.Escalated && this._raiseOnEscalation) {
      throw new EscalationRaised(
        `execution escalated at pressure ${this._execution.engine.pressure.toFixed(3)}`,
      );
    }

    const response = await this.raw.send(command);
    this._account(command, response);
    return response;
  }

  private _account(
    command: BedrockCommandLike,
    response: BedrockConverseResponse | BedrockInvokeResponse,
  ): void {
    const commandName = command.constructor.name;
    const modelId = command.input?.modelId ?? "unknown";

    // Converse / ConverseStream: usage is on the response directly
    if ("usage" in response && response.usage) {
      const usage = response.usage;
      const tokens =
        Number(usage.totalTokens ?? 0) ||
        Number(usage.inputTokens ?? 0) + Number(usage.outputTokens ?? 0);

      let toolCalls = 0;
      for (const block of response.output?.message?.content ?? []) {
        if ((block as { toolUse?: unknown }).toolUse) toolCalls += 1;
      }

      this._execution.recordStep({
        tokens,
        tool_calls: toolCalls,
        tag: `bedrock.${commandName}:${modelId}`,
      });
      return;
    }

    // InvokeModel: body is opaque per provider. Try to parse JSON and
    // extract provider-specific usage fields.
    if ("body" in response && response.body) {
      const bodyStr =
        typeof response.body === "string"
          ? response.body
          : new TextDecoder().decode(response.body);
      const tokens = extractTokensFromInvokeBody(bodyStr, modelId);
      this._execution.recordStep({
        tokens,
        tool_calls: 0, // tool detection is provider-specific; leave to caller
        tag: `bedrock.${commandName}:${modelId}`,
      });
      return;
    }

    // Fallback: count one step with zero tokens so the step shows up in audit
    this._execution.recordStep({
      tokens: 0,
      tool_calls: 0,
      tag: `bedrock.${commandName}:${modelId}`,
    });
  }
}

/**
 * Best-effort token extraction from InvokeModel response bodies. Returns
 * 0 if no recognized usage shape is present.
 */
export function extractTokensFromInvokeBody(body: string, modelId: string): number {
  let parsed: Record<string, unknown>;
  try {
    parsed = JSON.parse(body);
  } catch {
    return 0;
  }

  // Anthropic Claude on Bedrock
  if (typeof parsed.usage === "object" && parsed.usage !== null) {
    const u = parsed.usage as Record<string, unknown>;
    const inp = Number(u.input_tokens ?? 0);
    const out = Number(u.output_tokens ?? 0);
    if (inp || out) return inp + out;
  }

  // Amazon Titan
  const titanIn = (parsed as { inputTextTokenCount?: number }).inputTextTokenCount;
  if (typeof titanIn === "number") {
    const titanOut = (parsed as { results?: Array<{ tokenCount?: number }> }).results
      ?.reduce((acc, r) => acc + (r.tokenCount ?? 0), 0) ?? 0;
    return titanIn + titanOut;
  }

  // Meta Llama
  const llamaIn = (parsed as { prompt_token_count?: number }).prompt_token_count;
  const llamaOut = (parsed as { generation_token_count?: number })
    .generation_token_count;
  if (typeof llamaIn === "number" || typeof llamaOut === "number") {
    return (llamaIn ?? 0) + (llamaOut ?? 0);
  }

  // Cohere Command on Bedrock (top-level token_count)
  const cohereTokens = (parsed as { token_count?: { total_tokens?: number } })
    .token_count?.total_tokens;
  if (typeof cohereTokens === "number") return cohereTokens;

  void modelId; // reserved for future model-specific dispatch
  return 0;
}
