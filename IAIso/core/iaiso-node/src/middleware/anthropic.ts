/**
 * Anthropic middleware.
 *
 * Wraps an `@anthropic-ai/sdk` `Anthropic` client so that every call to
 * `.messages.create()` is accounted for in a `BoundedExecution`. Tokens
 * are read from the response's `usage` field; tool calls are counted
 * from response `content` blocks of type `"tool_use"`.
 *
 * Install:
 *   npm install @anthropic-ai/sdk
 *
 * Example:
 *   import Anthropic from "@anthropic-ai/sdk";
 *   import { BoundedExecution, AnthropicBoundedClient } from "@iaiso/core";
 *
 *   const raw = new Anthropic();
 *   await BoundedExecution.run({ config, audit_sink }, async (exec) => {
 *     const client = new AnthropicBoundedClient(raw, exec);
 *     const msg = await client.messages.create({
 *       model: "claude-opus-4-7",
 *       max_tokens: 1024,
 *       messages: [{ role: "user", content: "hello" }],
 *     });
 *   });
 *
 * If the execution is LOCKED or `raiseOnEscalation` is true and the engine
 * has escalated, calls throw `ExecutionLocked` or `EscalationRaised`
 * BEFORE reaching the Anthropic API.
 */

import { BoundedExecution, ExecutionLocked } from "../core/execution.js";
import { StepOutcome } from "../core/types.js";

export class EscalationRaised extends Error {
  constructor(message: string) {
    super(message);
    this.name = "EscalationRaised";
  }
}

interface MessageResponse {
  usage?: {
    input_tokens?: number | null;
    output_tokens?: number | null;
  } | null;
  content?: Array<{ type?: string } | unknown> | null;
  model?: string;
}

interface AnthropicLike {
  messages: {
    create: (params: Record<string, unknown>) => Promise<MessageResponse> | MessageResponse;
  };
}

export interface AnthropicBoundedClientOptions {
  raiseOnEscalation?: boolean;
}

/**
 * Wraps an Anthropic client so calls account for pressure.
 *
 * The wrapper exposes the same `.messages.create()` surface as the
 * underlying Anthropic client. Methods not explicitly wrapped pass
 * through but are not accounted for; account for them manually via
 * `execution.recordStep({...})` at the call site.
 */
export class AnthropicBoundedClient<T extends AnthropicLike = AnthropicLike> {
  readonly raw: T;
  private readonly _execution: BoundedExecution;
  private readonly _raiseOnEscalation: boolean;
  readonly messages: {
    create: (params: Record<string, unknown>) => Promise<MessageResponse>;
  };

  constructor(
    client: T,
    execution: BoundedExecution,
    opts: AnthropicBoundedClientOptions = {},
  ) {
    this.raw = client;
    this._execution = execution;
    this._raiseOnEscalation = opts.raiseOnEscalation ?? false;

    const inner = client.messages;
    const execRef = this._execution;
    const raiseOnEsc = this._raiseOnEscalation;
    const accountFn = this._account.bind(this);

    this.messages = {
      async create(params: Record<string, unknown>): Promise<MessageResponse> {
        const pre = execRef.check();
        if (pre === StepOutcome.Locked) {
          throw new ExecutionLocked(
            `execution ${execRef.engine.execution_id} is locked`,
          );
        }
        if (pre === StepOutcome.Escalated && raiseOnEsc) {
          throw new EscalationRaised(
            `execution escalated at pressure ${execRef.engine.pressure.toFixed(3)}`,
          );
        }
        const response = await inner.create(params);
        accountFn(response);
        return response;
      },
    };
  }

  private _account(response: MessageResponse): void {
    const usage = response.usage ?? null;
    const tokens =
      Number(usage?.input_tokens ?? 0) + Number(usage?.output_tokens ?? 0);

    let toolCalls = 0;
    const content = response.content ?? [];
    for (const block of content) {
      const blockType = (block as { type?: string })?.type;
      if (blockType === "tool_use") toolCalls += 1;
    }

    const model = response.model ?? "unknown";
    this._execution.recordStep({
      tokens,
      tool_calls: toolCalls,
      tag: `anthropic.messages.create:${model}`,
    });
  }
}
