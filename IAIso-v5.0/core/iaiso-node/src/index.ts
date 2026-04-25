/**
 * @iaiso/core — Node.js / TypeScript reference SDK for the IAIso framework.
 *
 * See:
 *   - https://github.com/SmartTasksOrg/IAISO — framework specification
 *   - spec/ — normative specification and conformance vectors
 *   - docs/CONFORMANCE.md — porting workflow for additional languages
 */

// Core
export {
  PressureConfig,
  PressureEngine,
  StepInput,
} from "./core/engine.js";
export type {
  PressureConfigInput,
  PressureEngineOptions,
  PressureSnapshot,
  StepInputInput,
} from "./core/engine.js";
export { Lifecycle, StepOutcome, defaultClock } from "./core/types.js";
export type { Clock } from "./core/types.js";
export {
  BoundedExecution,
  ExecutionLocked,
  ScopeRequired,
} from "./core/execution.js";
export type { BoundedExecutionOptions } from "./core/execution.js";

// Consent
export {
  ConsentScope,
  ConsentIssuer,
  ConsentVerifier,
  RevocationList,
  scopeGranted,
  generateHs256Secret,
  ConsentError,
  InvalidToken,
  ExpiredToken,
  RevokedToken,
  InsufficientScope,
} from "./consent/index.js";
export type {
  Algorithm,
  ConsentIssuerOptions,
  ConsentVerifierOptions,
} from "./consent/index.js";

// Audit
export {
  AuditEvent,
  SCHEMA_VERSION,
  MemorySink,
  NullSink,
  StdoutSink,
  FanoutSink,
  JsonlFileSink,
  WebhookSink,
} from "./audit/index.js";
export type {
  AuditEventJSON,
  AuditSink,
  WebhookSinkOptions,
} from "./audit/index.js";

// Policy
export {
  Policy,
  PolicyError,
  CoordinatorConfig,
  ConsentPolicy,
  SumAggregator,
  MeanAggregator,
  MaxAggregator,
  WeightedSumAggregator,
  validatePolicy,
  buildPolicy,
  loadPolicy,
} from "./policy/index.js";
export type {
  Aggregator,
  AggregatorName,
  CoordinatorConfigFields,
  ConsentPolicyFields,
} from "./policy/index.js";

// Middleware (peer-dep imports; only load if the peer is installed)
export {
  AnthropicBoundedClient,
  EscalationRaised,
  OpenAIBoundedClient,
  IaisoCallbackHandler,
  GeminiBoundedModel,
  BedrockBoundedClient,
  MistralBoundedClient,
  CohereBoundedClient,
  createLiteLLMClient,
} from "./middleware/index.js";
export type {
  AnthropicBoundedClientOptions,
  OpenAIBoundedClientOptions,
  GeminiBoundedModelOptions,
  BedrockBoundedClientOptions,
  MistralBoundedClientOptions,
  CohereBoundedClientOptions,
  LiteLLMClientOptions,
} from "./middleware/index.js";

// Coordination
export {
  SharedPressureCoordinator,
  RedisCoordinator,
  UPDATE_AND_FETCH_SCRIPT,
  parseHgetallFlat,
} from "./coordination/index.js";
export type {
  CoordinatorCallbacks,
  CoordinatorLifecycle,
  CoordinatorSnapshot,
  SharedPressureCoordinatorOptions,
  RedisClientLike,
  RedisCoordinatorOptions,
} from "./coordination/index.js";

// Identity (OIDC)
export {
  OIDCVerifier,
  OIDCError,
  OIDCNetworkError,
  oktaConfig,
  auth0Config,
  azureAdConfig,
  deriveScopes,
  issueFromOidc,
} from "./identity/index.js";
export type {
  OIDCProviderConfig,
  ScopeMapping,
} from "./identity/index.js";

// Metrics
export { PrometheusMetricsSink } from "./metrics/index.js";
export type { PrometheusMetricsSinkOptions } from "./metrics/index.js";

// Tracing
export { OtelSpanSink } from "./observability/index.js";
export type { OtelSpanSinkOptions } from "./observability/index.js";

export const VERSION = "0.3.0";
