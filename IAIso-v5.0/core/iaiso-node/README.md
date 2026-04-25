# @iaiso/core

**Node.js / TypeScript reference SDK for the IAIso bounded-agent-execution framework.**

IAIso adds pressure-based rate limiting, scope-based authorization, and structured
audit logging to LLM agent loops. This package is the TypeScript implementation of
the framework's runtime layer, conformant to **IAIso spec 1.0**.

> Targets the normative specification shipped in [`./spec/`](./spec/). Passes all 67
> spec conformance vectors plus 104 unit tests. Built alongside the Python reference
> SDK in [`iaiso`](https://github.com/SmartTasksOrg/IAISO/tree/main/core); both
> implementations produce identical event streams and consent tokens for identical
> inputs.

## Install

```bash
npm install @iaiso/core
```

Requires Node.js **≥ 20**.

### Optional peer dependencies

Install only what you use:

```bash
# LLM middleware
npm install @anthropic-ai/sdk           # AnthropicBoundedClient
npm install openai                      # OpenAIBoundedClient (+ OpenAI-compatible servers, LiteLLM proxy)
npm install @langchain/core             # IaisoCallbackHandler
npm install @google/generative-ai       # GeminiBoundedModel
npm install @aws-sdk/client-bedrock-runtime  # BedrockBoundedClient
npm install @mistralai/mistralai        # MistralBoundedClient
npm install cohere-ai                   # CohereBoundedClient

# Distributed coordination
npm install ioredis                     # RedisCoordinator

# OIDC identity
npm install jose                        # OIDCVerifier (Okta, Auth0, Azure AD, generic)

# Metrics & tracing
npm install prom-client                 # PrometheusMetricsSink
npm install @opentelemetry/api          # OtelSpanSink

# YAML policy files
npm install js-yaml                     # loadPolicyYaml / parsePolicyYaml
```

## Quick start

### Callback style (recommended)

```typescript
import {
  BoundedExecution,
  PressureConfig,
  StdoutSink,
} from "@iaiso/core";

await BoundedExecution.run(
  {
    config: new PressureConfig(),
    audit_sink: new StdoutSink(),
  },
  async (exec) => {
    while (!done) {
      if (exec.check() === "escalated") {
        await escalateToHuman();
        exec.reset();
        continue;
      }
      exec.requireScope("tools.search");
      const result = await runTool("search", query);
      exec.recordToolCall({ name: "search", tokens: result.tokenCount });
    }
  },
);
```

### Explicit lifecycle

```typescript
const exec = BoundedExecution.start({
  config: new PressureConfig(),
  audit_sink: auditSink,
});
try {
  exec.recordToolCall({ name: "search" });
  // ...
} finally {
  exec.close();
}
```

### Consent tokens

```typescript
import { ConsentIssuer, ConsentVerifier } from "@iaiso/core";

const issuer = new ConsentIssuer({
  signing_key: process.env.IAISO_HS256_SECRET!,
  algorithm: "HS256",
  issuer: "my-org",
});

const scope = issuer.issue({
  subject: "user-42",
  scopes: ["tools.search", "tools.fetch"],
  ttl_seconds: 3600,
  execution_id: "exec-abc",
});

// Later, in a verifier process:
const verifier = new ConsentVerifier({
  verification_key: process.env.IAISO_HS256_SECRET!,
  algorithm: "HS256",
  issuer: "my-org",
});
const verified = verifier.verify(scope.token, { execution_id: "exec-abc" });
verified.require("tools.search"); // throws InsufficientScope on denial
```

### Audit sinks

```typescript
import {
  FanoutSink,
  JsonlFileSink,
  StdoutSink,
  WebhookSink,
} from "@iaiso/core";

const sink = new FanoutSink([
  new StdoutSink(),
  new JsonlFileSink("./iaiso-audit.jsonl"),
  new WebhookSink({
    url: "https://siem.example.com/ingest",
    headers: { Authorization: "Bearer ..." },
  }),
]);
```

### Policy files

```typescript
import { loadPolicy } from "@iaiso/core";

const policy = loadPolicy("./iaiso.policy.json");
// policy.pressure, policy.coordinator, policy.consent, policy.aggregator, policy.metadata
```

## LLM middleware

Wrap provider SDK clients so every call is accounted for in a `BoundedExecution`.
Tokens and tool calls are accounted automatically; if the execution is locked
or escalated, calls fail fast before hitting the provider.

### Anthropic

```typescript
import Anthropic from "@anthropic-ai/sdk";
import { BoundedExecution, AnthropicBoundedClient } from "@iaiso/core";

const raw = new Anthropic();
await BoundedExecution.run({ config, audit_sink }, async (exec) => {
  const client = new AnthropicBoundedClient(raw, exec);
  const msg = await client.messages.create({
    model: "claude-opus-4-7",
    max_tokens: 1024,
    messages: [{ role: "user", content: "hello" }],
  });
});
```

### OpenAI (and OpenAI-compatible servers)

Works with vanilla OpenAI, vLLM, TGI, LiteLLM proxy, Together AI, Groq, and
any other server exposing the OpenAI chat-completions surface.

```typescript
import OpenAI from "openai";
import { BoundedExecution, OpenAIBoundedClient } from "@iaiso/core";

const raw = new OpenAI();
await BoundedExecution.run({ config, audit_sink }, async (exec) => {
  const client = new OpenAIBoundedClient(raw, exec);
  const resp = await client.chat.completions.create({
    model: "gpt-4o",
    messages: [{ role: "user", content: "hello" }],
  });
});
```

### LangChain

`IaisoCallbackHandler` hooks into `@langchain/core` via the standard callback
API. Works with any LangChain-compatible model or runnable.

```typescript
import { ChatAnthropic } from "@langchain/anthropic";
import { BoundedExecution, IaisoCallbackHandler } from "@iaiso/core";

await BoundedExecution.run({ config, audit_sink }, async (exec) => {
  const handler = new IaisoCallbackHandler(exec);
  const model = new ChatAnthropic({ model: "claude-opus-4-7" });
  const response = await model.invoke(prompt, { callbacks: [handler] });
});
```

### Google Gemini

```typescript
import { GoogleGenerativeAI } from "@google/generative-ai";
import { BoundedExecution, GeminiBoundedModel } from "@iaiso/core";

const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY!);
await BoundedExecution.run({ config, audit_sink }, async (exec) => {
  const raw = genAI.getGenerativeModel({ model: "gemini-1.5-pro" });
  const model = new GeminiBoundedModel(raw, exec);
  const result = await model.generateContent("hello");
});
```

### AWS Bedrock

```typescript
import { BedrockRuntimeClient } from "@aws-sdk/client-bedrock-runtime";
import { BoundedExecution, BedrockBoundedClient } from "@iaiso/core";

const raw = new BedrockRuntimeClient({ region: "us-east-1" });
await BoundedExecution.run({ config, audit_sink }, async (exec) => {
  const client = new BedrockBoundedClient(raw, exec);
  // Converse API
  const resp = await client.converse({
    modelId: "anthropic.claude-3-5-sonnet-20241022-v2:0",
    messages: [{ role: "user", content: [{ text: "hello" }] }],
  });
});
```

### Mistral

```typescript
import { Mistral } from "@mistralai/mistralai";
import { BoundedExecution, MistralBoundedClient } from "@iaiso/core";

const raw = new Mistral({ apiKey: process.env.MISTRAL_API_KEY! });
await BoundedExecution.run({ config, audit_sink }, async (exec) => {
  const client = new MistralBoundedClient(raw, exec);
  const resp = await client.chat.complete({
    model: "mistral-large-latest",
    messages: [{ role: "user", content: "hello" }],
  });
});
```

### Cohere

```typescript
import { CohereClient } from "cohere-ai";
import { BoundedExecution, CohereBoundedClient } from "@iaiso/core";

const raw = new CohereClient({ token: process.env.COHERE_API_KEY! });
await BoundedExecution.run({ config, audit_sink }, async (exec) => {
  const client = new CohereBoundedClient(raw, exec);
  const resp = await client.chat({ model: "command-r-plus", message: "hello" });
});
```

### LiteLLM

LiteLLM's Node surface is its proxy server, which exposes an OpenAI-compatible
endpoint. Point an OpenAI SDK client at the proxy and wrap it with
`OpenAIBoundedClient` — the `createLiteLLMClient` helper makes the pattern
explicit.

```typescript
import OpenAI from "openai";
import { BoundedExecution, OpenAIBoundedClient, createLiteLLMClient } from "@iaiso/core";

const raw = createLiteLLMClient(OpenAI, {
  baseURL: process.env.LITELLM_PROXY_URL!,
  apiKey: process.env.LITELLM_PROXY_KEY!,
});
await BoundedExecution.run({ config, audit_sink }, async (exec) => {
  const client = new OpenAIBoundedClient(raw, exec);
  const resp = await client.chat.completions.create({
    model: "claude-3-5-sonnet",   // any model your proxy routes
    messages: [{ role: "user", content: "hello" }],
  });
});
```

## Distributed coordination

Fleet-wide pressure aggregation across processes and hosts. The in-memory
coordinator handles a single process; the Redis coordinator is interoperable
with the Python reference's `RedisCoordinator` — workers on both runtimes can
share state by connecting to the same Redis instance with matching
`coordinator_id`.

```typescript
import Redis from "ioredis";
import {
  RedisCoordinator,
  SumAggregator,
} from "@iaiso/core";

const redis = new Redis(process.env.REDIS_URL!);
const coord = new RedisCoordinator({
  redis,
  coordinator_id: "prod-fleet",
  escalation_threshold: 5.0,
  release_threshold: 8.0,
  aggregator: new SumAggregator(),
  callbacks: {
    onEscalation: (snap) => alertOps(`fleet hot: ${snap.aggregate_pressure}`),
  },
});

await coord.register("worker-" + process.pid);
await coord.update("worker-" + process.pid, currentExecution.engine.pressure);
```

The Lua script used for atomic updates is exported as `UPDATE_AND_FETCH_SCRIPT`
and is verbatim from `spec/coordinator/README.md §1.2`.

## SIEM audit sinks

Ship audit events to Splunk HEC, Datadog Logs, Grafana Loki, Elasticsearch
(ECS), Sumo Logic, or New Relic. Payload shapes are exported as standalone
functions so operators can validate the wire format in isolation.

```typescript
import {
  FanoutSink,
  JsonlFileSink,
  SplunkHECSink,
  DatadogLogsSink,
  LokiSink,
  ElasticECSSink,
  SumoLogicSink,
  NewRelicLogsSink,
} from "@iaiso/core";

const sink = new FanoutSink([
  new JsonlFileSink("./iaiso-audit.jsonl"),
  new SplunkHECSink({
    url: "https://splunk.example.com:8088/services/collector/event",
    token: process.env.SPLUNK_HEC_TOKEN!,
    index: "iaiso",
  }),
  new DatadogLogsSink({
    url: "https://http-intake.logs.datadoghq.com/api/v2/logs",
    apiKey: process.env.DD_API_KEY!,
    service: "iaiso",
    ddtags: "env:prod",
  }),
  new LokiSink({
    url: "https://logs.grafana.net/loki/api/v1/push",
    username: process.env.LOKI_USER,
    password: process.env.LOKI_KEY,
    labels: { job: "iaiso", env: "prod" },
  }),
  new ElasticECSSink({
    url: "https://es.example.com/iaiso-audit/_doc",
    apiKey: process.env.ELASTIC_API_KEY!,
    dataset: "iaiso.audit",
  }),
  new SumoLogicSink({
    url: process.env.SUMO_HTTP_SOURCE_URL!,
    sourceCategory: "iaiso/audit",
    sourceName: "iaiso-prod",
  }),
  new NewRelicLogsSink({
    apiKey: process.env.NEWRELIC_LICENSE_KEY!,
    service: "iaiso",
    hostname: os.hostname(),
  }),
]);
```

SIEM sink wire formats are validated against each vendor's documented payload
shape in the test suite. End-to-end verification against live ingest endpoints
is operator-run — typically a 30-minute exercise per vendor.

## OIDC identity

Verify access / ID tokens from Okta, Auth0, Azure AD / Entra, or any
conforming OIDC provider — then either enrich into a `ConsentScope` or mint
an IAIso-signed token from the OIDC identity.

```typescript
import {
  ConsentIssuer,
  OIDCVerifier,
  oktaConfig,
  issueFromOidc,
} from "@iaiso/core";

const verifier = new OIDCVerifier(
  oktaConfig({
    domain: "acme.okta.com",
    audience: "api://iaiso",
  }),
);

const issuer = new ConsentIssuer({
  signing_key: process.env.IAISO_HS256_SECRET!,
  algorithm: "HS256",
});

// In your auth middleware:
const scope = await issueFromOidc({
  verifier,
  issuer,
  token: oidcAccessToken,
  mapping: {
    directClaims: ["scp", "permissions"],
    groupToScopes: {
      engineers: ["tools.search", "tools.fetch"],
      admins: ["admin"],
    },
  },
  ttlSeconds: 3600,
  executionId: execId,
});

// `scope` is a ConsentScope you can now attach to BoundedExecution
// or pass across process boundaries via `scope.token`.
```

Preset factories are provided for Okta (`oktaConfig`), Auth0 (`auth0Config`),
and Azure AD / Entra (`azureAdConfig`); the generic `OIDCVerifier` works
against any OIDC provider by passing `discoveryUrl` (auto-fetches the JWKS
endpoint) or `jwksUrl` directly. JWKS results are cached per
`jose.createRemoteJWKSet` (default 10 minutes).

## Metrics and tracing

### Prometheus

`PrometheusMetricsSink` is an `AuditSink` that counts events, increments
escalation / release counters, and gauges pressure on every step. Wire it
into your sink fanout and expose `/metrics` via your HTTP framework.

```typescript
import * as promClient from "prom-client";
import { FanoutSink, PrometheusMetricsSink } from "@iaiso/core";

const metrics = new PrometheusMetricsSink({
  promClient,
  registry: promClient.register,
});
const auditSink = new FanoutSink([new JsonlFileSink("./audit.jsonl"), metrics]);

// In your server:
app.get("/metrics", async (req, res) => {
  res.set("Content-Type", promClient.register.contentType);
  res.end(await promClient.register.metrics());
});
```

Exposed metrics:

- `iaiso_events_total{kind}` — counter
- `iaiso_escalations_total` — counter
- `iaiso_releases_total` — counter
- `iaiso_pressure{execution_id}` — gauge
- `iaiso_step_delta` — histogram

### OpenTelemetry tracing

`OtelSpanSink` opens one span per execution and attaches every audit event
as a span event, closing the span on `execution.closed`. Combine with any
OpenTelemetry SDK (Jaeger, Tempo, Honeycomb, DataDog APM, etc.).

```typescript
import { trace } from "@opentelemetry/api";
import { FanoutSink, OtelSpanSink } from "@iaiso/core";

const tracer = trace.getTracer("iaiso", "1.0");
const otel = new OtelSpanSink({ tracer });
const auditSink = new FanoutSink([new JsonlFileSink("./audit.jsonl"), otel]);
```

Headline engine state (pressure, escalated, released) is mirrored onto the
span itself as attributes for easier backend querying.

## Admin CLI

Install the package and the `iaiso` bin is on your PATH:

```bash
# Policy
iaiso policy template ./iaiso.policy.json
iaiso policy validate ./iaiso.policy.json

# Consent (needs IAISO_HS256_SECRET in env)
iaiso consent issue user-42 tools.search,tools.fetch 3600
iaiso consent verify <token>

# Audit
iaiso audit tail ./iaiso-audit.jsonl
iaiso audit stats ./iaiso-audit.jsonl

# Coordinator smoke test
iaiso coordinator demo

# Conformance (alias for iaiso-conformance)
iaiso conformance ./spec
```

The CLI is intentionally small — it's for operators to debug and validate
configuration, not a replacement for a control plane. All commands exit
with non-zero status on failure, so they compose in shell pipelines and CI.

## YAML policies

```typescript
import { loadPolicyYaml } from "@iaiso/core";

const policy = loadPolicyYaml("./iaiso.policy.yaml");
```

Supports `.yaml`, `.yml`, and `.json` file extensions. YAML parsing uses
`js-yaml`; the same validation rules apply as for JSON.

## Core API surface

| Export | Purpose |
|---|---|
| `PressureEngine`, `PressureConfig`, `StepInput` | Pressure math, stateful |
| `BoundedExecution` | High-level facade (callback + explicit) |
| `ConsentIssuer`, `ConsentVerifier`, `ConsentScope`, `RevocationList` | JWT consent tokens |
| `AuditEvent`, `MemorySink`, `NullSink`, `StdoutSink`, `FanoutSink`, `JsonlFileSink`, `WebhookSink` | Event envelope + base sinks |
| `SplunkHECSink`, `DatadogLogsSink`, `LokiSink`, `ElasticECSSink`, `SumoLogicSink`, `NewRelicLogsSink` | SIEM sinks |
| `Policy`, `loadPolicy`, `loadPolicyYaml`, `buildPolicy`, `validatePolicy` | Policy-as-code |
| `AnthropicBoundedClient`, `OpenAIBoundedClient`, `IaisoCallbackHandler`, `GeminiBoundedModel`, `BedrockBoundedClient`, `MistralBoundedClient`, `CohereBoundedClient`, `createLiteLLMClient` | LLM middleware |
| `SharedPressureCoordinator`, `RedisCoordinator` | Cross-execution coordination |
| `SumAggregator`, `MeanAggregator`, `MaxAggregator`, `WeightedSumAggregator` | Coordinator aggregators |
| `OIDCVerifier`, `oktaConfig`, `auth0Config`, `azureAdConfig`, `deriveScopes`, `issueFromOidc` | OIDC identity |
| `PrometheusMetricsSink` | Metrics (prom-client) |
| `OtelSpanSink` | Distributed tracing (OpenTelemetry) |
| `Lifecycle`, `StepOutcome` | Enum-style string unions |
| `ExecutionLocked`, `ScopeRequired`, `InvalidToken`, `ExpiredToken`, `RevokedToken`, `InsufficientScope`, `PolicyError`, `ConsentError`, `EscalationRaised`, `OIDCError` | Error types |

## Conformance

This package ships the IAIso specification at `./spec/` and a conformance runner
that validates this implementation against it.

```bash
# From the package directory
npx iaiso-conformance

# Output:
# [PASS] pressure: 20/20
# [PASS] consent:  23/23
# [PASS] events:   7/7
# [PASS] policy:   17/17
#
# conformance: all 67 vectors passed
```

Or programmatically:

```typescript
import { runAll } from "@iaiso/core/conformance";

const results = runAll("./spec");
for (const [section, vectors] of Object.entries(results)) {
  const passed = vectors.filter((v) => v.passed).length;
  console.log(`${section}: ${passed}/${vectors.length}`);
}
```

### Float tolerance

Pressure math is specified to real-number semantics with a `1e-9` absolute
tolerance for floating-point implementations (see `spec/README.md`). This port
meets the tolerance with straightforward IEEE-754 evaluation; no special
ordering or extended-precision arithmetic is required.

### Cross-language parity

Events emitted by this port validate against the same JSON Schemas
(`spec/events/envelope.schema.json`, `spec/events/payloads.schema.json`) as
the Python reference. Consent tokens issued by this port verify against the
Python `ConsentVerifier` and vice versa, given the same key and algorithm.
Redis coordinator state is interoperable across both runtimes using the same
`(key_prefix, coordinator_id)` tuple.

## Scope

Shipping in `0.3.0`:

- **Pressure engine** with full lifecycle semantics
- **Consent tokens** (HS256 / RS256)
- **Audit event envelope** + 11 sinks: stdout, JSONL file, webhook, fanout, memory, Splunk HEC, Datadog Logs, Grafana Loki, Elastic Common Schema, Sumo Logic HTTP Source, New Relic Logs
- **Policy-as-code** loader (JSON + YAML)
- **BoundedExecution** facade with callback + explicit lifecycle patterns
- **LLM middleware**: Anthropic, OpenAI (+ OpenAI-compatible servers), LangChain, Google Gemini, AWS Bedrock, Mistral, Cohere, LiteLLM (via proxy)
- **Cross-execution coordination**: in-memory + Redis-backed (interoperable with Python)
- **OIDC identity**: Okta, Auth0, Azure AD/Entra presets + generic verifier; scope mapping + `issueFromOidc` flow
- **Metrics** (`PrometheusMetricsSink`) and **distributed tracing** (`OtelSpanSink`)
- **Admin CLI** (`iaiso`) — policy validate/template, consent issue/verify, audit tail/stats, coordinator demo, conformance
- **Conformance runner** with CLI (`iaiso-conformance`)

Planned in subsequent releases (see the main repository roadmap):

- Additional LLM middleware as providers evolve
- Coordinator gRPC sidecar (proto drafted in `spec/coordinator/wire.proto`)
- Additional conformant ports (Go, Rust, Java)

Composition with adjacent safety layers (Layer 0 process/hardware anchors,
Layer 4 escalation bridges, Layer 6 existential safeguards) is described in
the main framework specification at `../../vision/` in the repo.

## Development

```bash
npm install
npm run typecheck   # strict TypeScript
npm test            # 171 tests (104 unit + 67 conformance)
npm run build       # emit to dist/
npm run conformance # spec conformance CLI
```

### Project layout

```
iaiso-node/
├── src/
│   ├── core/              # engine, types, BoundedExecution
│   ├── consent/           # JWT issuer/verifier, scope matching
│   ├── audit/             # event envelope + 11 sinks
│   ├── policy/            # policy loader (JSON + YAML) + aggregators
│   ├── middleware/        # 8 LLM provider adapters
│   ├── coordination/      # in-memory + Redis coordinators
│   ├── identity/          # OIDC verification + scope mapping
│   ├── metrics/           # Prometheus sink
│   ├── observability/     # OpenTelemetry tracing sink
│   ├── cli/               # admin CLI implementation
│   └── conformance/       # vector runner
├── bin/
│   ├── iaiso.mjs                 # admin CLI entry
│   └── iaiso-conformance.mjs     # conformance CLI entry
├── tests/                 # 14 vitest files, 171 tests
├── spec/                  # normative specification (copy of repo-level spec/)
├── dist/                  # tsc output
└── package.json
```

### Contributing

Graduation from `vision/` designs to running code follows the main repo's
[contributing guide](https://github.com/SmartTasksOrg/IAISO/blob/main/core/docs/CONTRIBUTING.md).
Every PR must keep all 67 conformance vectors passing and add tests for the
new surface it introduces.

## Versioning

- Package version tracks SDK features (`0.1.0`, `0.2.0`, …).
- **Spec version** is `1.0`, defined in `./spec/VERSION`. A MINOR spec bump
  never breaks existing vectors; a MAJOR spec bump ships a migration guide.
- Breaking changes in the public API are signaled by a MAJOR package bump.

## License

Apache-2.0. See [`LICENSE`](./LICENSE).

## Links

- Main repository: https://github.com/SmartTasksOrg/IAISO
- Framework specification: `../../vision/README.md` in the repo
- Python reference SDK: `../iaiso-python/README.md` in the repo
- Conformance porting guide: `../docs/CONFORMANCE.md` in the repo
- Normative specification: `../spec/` in the repo
