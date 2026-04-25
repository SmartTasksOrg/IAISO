# iaiso-csharp

**C# / .NET reference SDK for the IAIso bounded-agent-execution framework.**

IAIso adds pressure-based rate limiting, scope-based authorization, and
structured audit logging to LLM agent loops. This is the C# / .NET
implementation, conformant to **IAIso spec 1.0**.

> Built on **.NET 8 (LTS)**. Multi-project solution with one assembly
> per capability so consumers add only what they need. Passes all
> **67 spec conformance vectors** plus **50 unit tests**. Wire-format
> compatible with the [Python](../iaiso-python/), [Node](../iaiso-node/),
> [Go](../iaiso-go/), [Rust](../iaiso-rust/), and [Java](../iaiso-java/)
> reference SDKs — same audit events, same JWTs, same Redis Lua script.

## Workspace layout

`Iaiso.sln` ties together a parent `Directory.Build.props` and 11 source
projects plus a test project:

```
iaiso-csharp/
├── Iaiso.sln
├── Directory.Build.props          # shared MSBuild settings (TFM, Nullable, Version)
├── NuGet.Config                   # used for offline / restricted environments
├── README.md, LICENSE, .gitignore
├── spec/                          # normative spec + conformance vectors
├── src/
│   ├── Iaiso.Audit/               # event envelope + base sinks
│   ├── Iaiso.Core/                # pressure engine + BoundedExecution
│   ├── Iaiso.Consent/             # JWT issuer/verifier (HS256/RS256)
│   ├── Iaiso.Policy/              # JSON policy loader
│   ├── Iaiso.Coordination/        # in-memory + Redis coordinator
│   ├── Iaiso.Middleware/          # 7 LLM provider wrappers (sub-namespaces)
│   ├── Iaiso.Identity/            # OIDC verifier + scope mapping
│   ├── Iaiso.Metrics/             # Prometheus sink (structural)
│   ├── Iaiso.Observability/       # OpenTelemetry sink (structural)
│   ├── Iaiso.Conformance/         # vector runner
│   └── Iaiso.Cli/                 # admin CLI (`iaiso` command)
└── tests/
    └── Iaiso.Tests/               # in-tree test runner (no external test framework)
```

## Install

Add the assemblies you need from NuGet:

```xml
<ItemGroup>
    <PackageReference Include="Iaiso.Core" Version="0.1.0" />
    <PackageReference Include="Iaiso.Consent" Version="0.1.0" />
</ItemGroup>
```

Or via the .NET CLI:

```bash
dotnet add package Iaiso.Core
dotnet add package Iaiso.Consent
```

Targets **net8.0** (LTS).

The SDK has **zero direct runtime dependencies**. JSON via
`System.Text.Json` (built-in), crypto via `System.Security.Cryptography`
(built-in), JWT signing/verification implemented in-house. LLM provider
clients, Redis, Prometheus, OpenTelemetry, and HTTP libraries are all
integrated via **structural interfaces**, so you plug in whichever
client library you prefer without IAIso pulling those packages into
your dep graph.

## Quick start

```csharp
using Iaiso.Audit;
using Iaiso.Core;

var sink = new MemorySink();
BoundedExecution.Run(
    new BoundedExecutionOptions { AuditSink = sink },
    exec =>
    {
        var outcome = exec.RecordToolCall("search", 500);
        if (outcome == StepOutcome.Escalated)
        {
            // Layer 4: request human review per the escalation template
        }
    });
```

Or with the `using` pattern:

```csharp
using var exec = BoundedExecution.Start(new BoundedExecutionOptions { AuditSink = sink });
exec.RecordTokens(500, "search");
```

## LLM middleware

Seven provider adapters under `Iaiso.Middleware.*`. Each provider
defines a structural `IClient` interface you satisfy with a thin
adapter around the upstream SDK:

```csharp
using Iaiso.Middleware.Anthropic;
using System.Text.Json.Nodes;

class MyAnthropicAdapter : AnthropicMiddleware.IClient
{
    // Wraps Anthropic.SDK, AWSSDK.BedrockRuntime, or any HTTP client.
    public AnthropicMiddleware.Response MessagesCreate(JsonObject parameters)
    {
        // ... call the upstream SDK, map into AnthropicMiddleware.Response
    }
}

var bounded = new AnthropicMiddleware.BoundedClient(
    new MyAnthropicAdapter(), exec, AnthropicMiddleware.Options.Defaults());
var resp = bounded.MessagesCreate(parameters);
```

The structural pattern keeps the SDK free of any specific provider
package. Adapters: `anthropic`, `openai` (works with any
OpenAI-compatible endpoint including Azure OpenAI, vLLM, TGI, LiteLLM
proxy, Together, Groq), `gemini`, `bedrock` (Converse + InvokeModel),
`mistral`, `cohere`, and `litellm` (proxy-pattern helper).

## Distributed coordination

In-memory:

```csharp
using Iaiso.Coordination;
using Iaiso.Policy;

var coord = SharedPressureCoordinator.CreateBuilder()
    .EscalationThreshold(5.0)
    .ReleaseThreshold(8.0)
    .Build();
coord.Register("worker-1");
coord.Update("worker-1", 0.4);
```

Redis-backed (interoperable with Python, Node, Go, Rust, and Java references):

```csharp
// IRedisClient is a structural interface — supply an adapter around
// StackExchange.Redis or any Redis client library.
var coord = RedisCoordinator.CreateBuilder()
    .Redis(myRedisAdapter)
    .CoordinatorId("prod-fleet")
    .EscalationThreshold(5.0)
    .ReleaseThreshold(8.0)
    .Build();
```

The Lua script used for atomic updates is exported as
`RedisCoordinator.UpdateAndFetchScript` and is verbatim from
`spec/coordinator/README.md §1.2`. **All six reference SDKs ship the
exact same script bytes** — Python, Node, Go, Rust, Java, C# —
guaranteeing fleet coordination across mixed-language environments.

## Audit sinks

The base sinks (`MemorySink`, `NullSink`, `StdoutSink`, `FanoutSink`,
`JsonlFileSink`) live in `Iaiso.Audit` and are always available.

> **Note on SIEM sinks**: SIEM-vendor sinks (Splunk HEC, Datadog Logs,
> Loki, Elasticsearch ECS, Sumo Logic, New Relic Logs) are documented
> and tested in the Python, Node, and Go references. The C# port ships
> with the base sinks only in 0.1.0; SIEM sinks are deferred to 0.2.0.
> For now, use `JsonlFileSink` plus a forwarder (Vector, Fluent Bit, or
> any log shipper), or implement a sink for your vendor in two methods —
> the `ISink` interface is just `void Emit(Event @event)`.

## OIDC identity

```csharp
using Iaiso.Identity;

var cfg = ProviderConfig.Okta("acme.okta.com", "api://my-resource");
// or: ProviderConfig.Auth0("acme.auth0.com", "api")
// or: ProviderConfig.AzureAd("tenant-id", "api://my-resource", v2: true)

var verifier = new OidcVerifier(cfg);

// Fetch JWKS bytes via HttpClient (or any HTTP library) then inject:
verifier.SetJwksFromBytes(jwksBytes);

var claims = verifier.Verify(idToken);
var scopes = OidcVerifier.DeriveScopes(claims, ScopeMapping.Defaults());
```

The library is HTTP-free — `SetJwksFromBytes()` takes pre-fetched bytes,
so users wire in their preferred HTTP client.

## Metrics and tracing

`Iaiso.Metrics` exposes `PrometheusSink` with structural
`ICounter`/`ICounterVec`/`IGauge`/`IGaugeVec`/`IHistogram` interfaces.
Adapt the official `prometheus-net` package.

`Iaiso.Observability` exposes `OtelSpanSink` with structural `ITracer`
and `ISpan` interfaces. Adapt the `OpenTelemetry` packages.

## Admin CLI

The CLI is a regular .NET executable project. Build and run:

```bash
dotnet build -c Release
dotnet run --project src/Iaiso.Cli -- --help
```

```
iaiso policy validate ./iaiso.policy.json
iaiso policy template ./iaiso.policy.json
iaiso consent issue user-42 tools.search,tools.fetch 3600  # needs IAISO_HS256_SECRET
iaiso consent verify <token>
iaiso audit tail ./iaiso-audit.jsonl
iaiso audit stats ./iaiso-audit.jsonl
iaiso coordinator demo
iaiso conformance ./spec
```

For a single-file deployment:

```bash
dotnet publish src/Iaiso.Cli -c Release -r linux-x64 --self-contained false /p:PublishSingleFile=true
./src/Iaiso.Cli/bin/Release/net8.0/linux-x64/publish/iaiso --help
```

## Conformance

```bash
dotnet test                                        # build + run all 50 unit tests + 67 spec vectors
dotnet run --project src/Iaiso.Cli -- conformance ./spec  # via the CLI
```

Or programmatically:

```csharp
using Iaiso.Conformance;

var results = ConformanceRunner.RunAll("./spec");
Console.WriteLine($"{results.CountPassed}/{results.CountTotal}");
```

### Float tolerance

Pressure math is specified to real-number semantics with a `1e-9`
absolute tolerance for floating-point implementations
(see `spec/README.md`). This port meets the tolerance with
straightforward IEEE-754 evaluation in `double`.

### Cross-language parity

Audit events emitted by this port serialize byte-identically to the
Python, Node, Go, Rust, and Java references for the same input. JWTs
issued by this port verify against every other reference SDK's verifier
given the same key and algorithm. Redis coordinator state is
interoperable across all six runtimes using the same
`(KeyPrefix, CoordinatorId)` tuple.

## Development

```bash
dotnet restore
dotnet build
dotnet test
```

The repo's `tests/Iaiso.Tests/` project is an executable that contains
its own tiny in-tree test runner (reflection-based discovery of methods
named `Test*` on classes ending in `Tests`). This avoids any external
test framework dependency and lets the suite run identically in
restricted environments. To run it directly:

```bash
dotnet run --project tests/Iaiso.Tests
```

## Versioning

- Assembly versions track SDK features (`0.1.0`, `0.2.0`, …).
- **Spec version** is `1.0`, defined in `./spec/VERSION`. A MINOR spec
  bump never breaks existing vectors; a MAJOR spec bump ships a
  migration guide.
- Breaking changes in the public API are signaled by a MAJOR assembly
  version bump.

## Notable engineering decisions

1. **Zero runtime dependencies.** JSON via `System.Text.Json`, crypto via
   `System.Security.Cryptography`, JWT hand-rolled (~150 lines, constant-time
   signature comparison via XOR). Every external integration point —
   Redis, Prometheus, OpenTelemetry, LLM providers, HTTP clients — is
   wired through structural interfaces (`IRedisClient`,
   `OtelSpanSink.ITracer`, `PrometheusSink.ICounter`, each provider's
   `IClient`) that consumers satisfy with thin adapters.
2. **JSON-only policies.** `System.Text.Json` doesn't ship with YAML
   support and the C# port intentionally stays dependency-light. Convert
   YAML externally if needed (the Python CLI's `iaiso policy template`
   outputs JSON, or use `yq -o=j`).
3. **Stable JSON key order via hand-built serialization.** `Event.ToJson()`
   writes fields in spec order (`schema_version, execution_id, kind,
   timestamp, data`); the `data` payload uses `SortedDictionary` for
   alphabetical key sort; integer doubles serialize as `0` not `0.0`
   to match the wire format of the other reference ports.
4. **Builder pattern throughout.** `PressureConfig.CreateBuilder()`,
   `Issuer.CreateBuilder()`, `RedisCoordinator.CreateBuilder()` — fluent
   chains with `WithX()` style methods and defaults baked into builders.
5. **Lifecycle/StepOutcome as enums with extension methods for wire format.**
   `Lifecycle.Running.Wire() == "running"` (lowercase wire format).
   Cross-language wire compatibility maintained.
6. **Sub-namespaces under `Iaiso.Middleware`** — `Iaiso.Middleware.Anthropic`,
   `Iaiso.Middleware.OpenAi`, etc. — each with its own provider client,
   bounded wrapper, and options. All in a single assembly so consumers
   get one package reference.
7. **In-tree test runner.** `tests/Iaiso.Tests/` is an `Exe` that
   reflection-discovers `Test*` methods on `*Tests` classes. No xUnit /
   NUnit / MSTest dependency — works in any environment, restricted
   network or not.

## License

Apache-2.0. See [LICENSE](LICENSE).

## Links

- Main repository: https://github.com/SmartTasksOrg/IAISO
- Framework specification: `../../vision/README.md` in the repo
- Python reference SDK: `../iaiso-python/README.md`
- Node.js / TypeScript reference SDK: `../iaiso-node/README.md`
- Go reference SDK: `../iaiso-go/README.md`
- Rust reference SDK: `../iaiso-rust/README.md`
- Java reference SDK: `../iaiso-java/README.md`
- Conformance porting guide: `../docs/CONFORMANCE.md`
- Normative specification: `../spec/`
