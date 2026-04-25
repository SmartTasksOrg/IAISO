/**
 * Google Gemini / Vertex AI middleware.
 *
 * Wraps `@google/generative-ai` so calls to `model.generateContent()`
 * are accounted for in a `BoundedExecution`. Token counts come from
 * `response.usageMetadata`; tool/function calls are counted from
 * candidate parts of type `functionCall`.
 *
 * Install:
 *   npm install @google/generative-ai
 *
 * Example:
 *   import { GoogleGenerativeAI } from "@google/generative-ai";
 *   import { BoundedExecution, GeminiBoundedModel } from "@iaiso/core";
 *
 *   const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY!);
 *   await BoundedExecution.run({ config, audit_sink }, async (exec) => {
 *     const raw = genAI.getGenerativeModel({ model: "gemini-1.5-pro" });
 *     const model = new GeminiBoundedModel(raw, exec);
 *     const result = await model.generateContent("hello");
 *   });
 */

import { BoundedExecution, ExecutionLocked } from "../core/execution.js";
import { StepOutcome } from "../core/types.js";
import { EscalationRaised } from "./anthropic.js";

interface GeminiResponse {
  response?: {
    usageMetadata?: {
      promptTokenCount?: number;
      candidatesTokenCount?: number;
      totalTokenCount?: number;
    };
    candidates?: Array<{
      content?: {
        parts?: Array<{ functionCall?: unknown; text?: string }>;
      };
    }>;
  };
  usageMetadata?: {
    promptTokenCount?: number;
    candidatesTokenCount?: number;
    totalTokenCount?: number;
  };
  candidates?: Array<{
    content?: {
      parts?: Array<{ functionCall?: unknown; text?: string }>;
    };
  }>;
}

interface GeminiGenerativeModelLike {
  generateContent: (
    request: string | object,
  ) => Promise<GeminiResponse> | GeminiResponse;
  model?: string;
}

export interface GeminiBoundedModelOptions {
  raiseOnEscalation?: boolean;
}

export class GeminiBoundedModel<
  T extends GeminiGenerativeModelLike = GeminiGenerativeModelLike,
> {
  readonly raw: T;
  private readonly _execution: BoundedExecution;
  private readonly _raiseOnEscalation: boolean;

  constructor(
    model: T,
    execution: BoundedExecution,
    opts: GeminiBoundedModelOptions = {},
  ) {
    this.raw = model;
    this._execution = execution;
    this._raiseOnEscalation = opts.raiseOnEscalation ?? false;
  }

  async generateContent(request: string | object): Promise<GeminiResponse> {
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
    const response = await this.raw.generateContent(request);
    this._account(response);
    return response;
  }

  private _account(resp: GeminiResponse): void {
    // Gemini responses sometimes nest under `.response`; accept both shapes
    const inner = resp.response ?? resp;
    const usage = inner.usageMetadata ?? {};
    const tokens =
      Number(usage.totalTokenCount ?? 0) ||
      Number(usage.promptTokenCount ?? 0) +
        Number(usage.candidatesTokenCount ?? 0);

    let toolCalls = 0;
    for (const cand of inner.candidates ?? []) {
      for (const part of cand.content?.parts ?? []) {
        if ((part as { functionCall?: unknown }).functionCall) toolCalls += 1;
      }
    }

    const model = this.raw.model ?? "gemini";
    this._execution.recordStep({
      tokens,
      tool_calls: toolCalls,
      tag: `gemini.generateContent:${model}`,
    });
  }
}
