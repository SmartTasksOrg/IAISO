/**
 * OpenAI middleware.
 *
 * Wraps the `openai` Node SDK so calls to `.chat.completions.create()`
 * and `.responses.create()` (where available) are accounted for in a
 * BoundedExecution. Also works with OpenAI-compatible servers (vLLM,
 * TGI, LiteLLM proxy, Together AI, Groq, etc.) — point the underlying
 * client at the compatible endpoint.
 *
 * Install:
 *   npm install openai
 */

import { BoundedExecution, ExecutionLocked } from "../core/execution.js";
import { StepOutcome } from "../core/types.js";
import { EscalationRaised } from "./anthropic.js";

interface OpenAIChatResponse {
  usage?: {
    prompt_tokens?: number | null;
    completion_tokens?: number | null;
    total_tokens?: number | null;
  } | null;
  choices?: Array<{
    message?: {
      tool_calls?: Array<unknown> | null;
      function_call?: unknown;
    };
  }> | null;
  model?: string;
}

interface OpenAILike {
  chat: {
    completions: {
      create: (params: Record<string, unknown>) => Promise<OpenAIChatResponse> | OpenAIChatResponse;
    };
  };
}

export interface OpenAIBoundedClientOptions {
  raiseOnEscalation?: boolean;
}

export class OpenAIBoundedClient<T extends OpenAILike = OpenAILike> {
  readonly raw: T;
  private readonly _execution: BoundedExecution;
  private readonly _raiseOnEscalation: boolean;
  readonly chat: {
    completions: {
      create: (params: Record<string, unknown>) => Promise<OpenAIChatResponse>;
    };
  };

  constructor(
    client: T,
    execution: BoundedExecution,
    opts: OpenAIBoundedClientOptions = {},
  ) {
    this.raw = client;
    this._execution = execution;
    this._raiseOnEscalation = opts.raiseOnEscalation ?? false;

    const innerCompletions = client.chat.completions;
    const execRef = this._execution;
    const raiseOnEsc = this._raiseOnEscalation;
    const accountFn = this._account.bind(this);

    this.chat = {
      completions: {
        async create(params: Record<string, unknown>): Promise<OpenAIChatResponse> {
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
          const response = await innerCompletions.create(params);
          accountFn(response);
          return response;
        },
      },
    };
  }

  private _account(response: OpenAIChatResponse): void {
    const usage = response.usage ?? null;
    const tokens =
      Number(usage?.total_tokens ?? 0) ||
      Number(usage?.prompt_tokens ?? 0) + Number(usage?.completion_tokens ?? 0);

    let toolCalls = 0;
    const choices = response.choices ?? [];
    for (const choice of choices) {
      const msg = choice?.message;
      if (msg?.tool_calls && Array.isArray(msg.tool_calls)) {
        toolCalls += msg.tool_calls.length;
      } else if (msg?.function_call) {
        toolCalls += 1;
      }
    }

    const model = response.model ?? "unknown";
    this._execution.recordStep({
      tokens,
      tool_calls: toolCalls,
      tag: `openai.chat.completions.create:${model}`,
    });
  }
}
