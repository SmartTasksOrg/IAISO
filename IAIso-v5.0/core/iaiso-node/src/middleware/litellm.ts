/**
 * LiteLLM integration.
 *
 * LiteLLM's Node story is different from Python: the primary integration
 * surface is the **LiteLLM proxy server**, which exposes an
 * OpenAI-compatible endpoint that routes to any of 100+ underlying
 * providers. On the client side, you point the OpenAI SDK at the proxy
 * URL and IAIso accounts for the call via `OpenAIBoundedClient` — token
 * accounting from the proxy's OpenAI-shaped `usage` field works
 * identically to accounting against OpenAI directly.
 *
 * This module exposes a tiny factory that makes the integration pattern
 * obvious in code. It is a thin helper; the actual accounting is done
 * by `OpenAIBoundedClient`.
 *
 * Install:
 *   npm install openai     # the client library
 *   # (LiteLLM itself is deployed as a server; no client package required.)
 *
 * Example:
 *   import OpenAI from "openai";
 *   import { createLiteLLMClient } from "@iaiso/core";
 *
 *   const client = createLiteLLMClient(OpenAI, {
 *     baseURL: process.env.LITELLM_PROXY_URL!,
 *     apiKey: process.env.LITELLM_PROXY_KEY!,
 *   });
 *
 *   await BoundedExecution.run({ config, audit_sink }, async (exec) => {
 *     const bounded = new OpenAIBoundedClient(client, exec);
 *     const resp = await bounded.chat.completions.create({
 *       model: "claude-3-5-sonnet",  // or any model the proxy routes to
 *       messages: [{ role: "user", content: "hello" }],
 *     });
 *   });
 */

export interface LiteLLMClientOptions {
  /** Base URL of the LiteLLM proxy server (e.g. "https://llm.example.com"). */
  baseURL: string;
  /** Master key or virtual key provisioned in the LiteLLM proxy. */
  apiKey: string;
  /** Additional headers, e.g. tenancy / tracing. */
  defaultHeaders?: Record<string, string>;
}

/**
 * Construct an OpenAI SDK client pointed at a LiteLLM proxy.
 *
 * Typed as an `OpenAI`-constructor factory to avoid hard-importing the
 * `openai` package. Pass the class (`OpenAI` default export) and an
 * options bag; returns an instance.
 */
export function createLiteLLMClient<T, C extends new (opts: unknown) => T>(
  OpenAICtor: C,
  opts: LiteLLMClientOptions,
): T {
  return new OpenAICtor({
    baseURL: opts.baseURL,
    apiKey: opts.apiKey,
    defaultHeaders: opts.defaultHeaders,
  });
}
