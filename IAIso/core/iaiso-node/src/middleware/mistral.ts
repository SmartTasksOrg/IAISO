/**
 * Mistral middleware.
 *
 * Wraps `@mistralai/mistralai` so every `.chat.complete()` call is
 * accounted for in a `BoundedExecution`. Tokens from
 * `response.usage.totalTokens`; tool calls from
 * `response.choices[].message.toolCalls[]`.
 *
 * Install:
 *   npm install @mistralai/mistralai
 */

import { BoundedExecution, ExecutionLocked } from "../core/execution.js";
import { StepOutcome } from "../core/types.js";
import { EscalationRaised } from "./anthropic.js";

interface MistralChatResponse {
  usage?: {
    promptTokens?: number | null;
    completionTokens?: number | null;
    totalTokens?: number | null;
  } | null;
  choices?: Array<{
    message?: {
      toolCalls?: Array<unknown> | null;
      tool_calls?: Array<unknown> | null;
    };
  }> | null;
  model?: string;
}

interface MistralLike {
  chat: {
    complete: (params: Record<string, unknown>) => Promise<MistralChatResponse> | MistralChatResponse;
  };
}

export interface MistralBoundedClientOptions {
  raiseOnEscalation?: boolean;
}

export class MistralBoundedClient<T extends MistralLike = MistralLike> {
  readonly raw: T;
  private readonly _execution: BoundedExecution;
  private readonly _raiseOnEscalation: boolean;
  readonly chat: {
    complete: (params: Record<string, unknown>) => Promise<MistralChatResponse>;
  };

  constructor(
    client: T,
    execution: BoundedExecution,
    opts: MistralBoundedClientOptions = {},
  ) {
    this.raw = client;
    this._execution = execution;
    this._raiseOnEscalation = opts.raiseOnEscalation ?? false;

    const innerChat = client.chat;
    const execRef = execution;
    const raiseOnEsc = this._raiseOnEscalation;
    const accountFn = this._account.bind(this);

    this.chat = {
      async complete(params: Record<string, unknown>): Promise<MistralChatResponse> {
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
        const response = await innerChat.complete(params);
        accountFn(response);
        return response;
      },
    };
  }

  private _account(response: MistralChatResponse): void {
    const usage = response.usage ?? null;
    const tokens =
      Number(usage?.totalTokens ?? 0) ||
      Number(usage?.promptTokens ?? 0) + Number(usage?.completionTokens ?? 0);

    let toolCalls = 0;
    for (const choice of response.choices ?? []) {
      const msg = choice?.message;
      const calls = msg?.toolCalls ?? msg?.tool_calls;
      if (Array.isArray(calls)) toolCalls += calls.length;
    }

    const model = response.model ?? "unknown";
    this._execution.recordStep({
      tokens,
      tool_calls: toolCalls,
      tag: `mistral.chat.complete:${model}`,
    });
  }
}
