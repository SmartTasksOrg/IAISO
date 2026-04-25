/**
 * Cohere middleware.
 *
 * Wraps the `cohere-ai` Node SDK's `.chat()` method. Tokens read from
 * `response.meta.tokens` (inputTokens + outputTokens) or the newer
 * `response.meta.billed_units`/`billedUnits` shape. Tool calls counted
 * from `response.toolCalls`.
 *
 * Install:
 *   npm install cohere-ai
 */

import { BoundedExecution, ExecutionLocked } from "../core/execution.js";
import { StepOutcome } from "../core/types.js";
import { EscalationRaised } from "./anthropic.js";

interface CohereTokens {
  inputTokens?: number | null;
  outputTokens?: number | null;
  input_tokens?: number | null;
  output_tokens?: number | null;
}

interface CohereChatResponse {
  meta?: {
    tokens?: CohereTokens;
    billedUnits?: CohereTokens;
    billed_units?: CohereTokens;
  } | null;
  toolCalls?: Array<unknown> | null;
  tool_calls?: Array<unknown> | null;
  model?: string;
}

interface CohereLike {
  chat: (
    params: Record<string, unknown>,
  ) => Promise<CohereChatResponse> | CohereChatResponse;
}

export interface CohereBoundedClientOptions {
  raiseOnEscalation?: boolean;
}

export class CohereBoundedClient<T extends CohereLike = CohereLike> {
  readonly raw: T;
  private readonly _execution: BoundedExecution;
  private readonly _raiseOnEscalation: boolean;

  constructor(
    client: T,
    execution: BoundedExecution,
    opts: CohereBoundedClientOptions = {},
  ) {
    this.raw = client;
    this._execution = execution;
    this._raiseOnEscalation = opts.raiseOnEscalation ?? false;
  }

  async chat(params: Record<string, unknown>): Promise<CohereChatResponse> {
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
    const response = await this.raw.chat(params);
    this._account(response);
    return response;
  }

  private _account(response: CohereChatResponse): void {
    const meta = response.meta ?? null;
    const bucket = meta?.tokens ?? meta?.billedUnits ?? meta?.billed_units;
    const input = Number(bucket?.inputTokens ?? bucket?.input_tokens ?? 0);
    const output = Number(bucket?.outputTokens ?? bucket?.output_tokens ?? 0);
    const tokens = input + output;

    const calls = response.toolCalls ?? response.tool_calls;
    const toolCalls = Array.isArray(calls) ? calls.length : 0;

    const model = response.model ?? "unknown";
    this._execution.recordStep({
      tokens,
      tool_calls: toolCalls,
      tag: `cohere.chat:${model}`,
    });
  }
}
