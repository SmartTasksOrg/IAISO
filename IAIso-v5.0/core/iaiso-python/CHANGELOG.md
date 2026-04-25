# Changelog

All notable changes to IAIso are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); version
numbering follows the policy in `docs/BACKWARDS_COMPATIBILITY.md`.

## [Unreleased]

### Added — Ruby reference port (RubyGems, `iaiso@0.1.0`)

The roadmap's Ruby port has shipped. A ninth reference SDK joins the
eight prior ports, with full feature parity against the runtime layer
and **67/67 conformance vectors green plus 54 Minitest unit tests
(109 assertions) all passing on first run**.

**Single gem `iaiso`** with capabilities cleanly separated into
modules under `IAIso::*`, autoloaded so consumers pay only for what
they require. Targets **Ruby 3.0+**. ~3,200 lines of source code
across 47 source files plus 9 Minitest test files.

**Module layout** (single gem, autoloaded submodules)

- `IAIso::Audit` — `Event` envelope with hand-built canonical-JSON
  serialization (field order matches spec, alphabetical `data` key
  sorting, integer-valued floats emit as integers); `Sink` contract;
  5 sinks (Memory, Null, Stdout, Fanout, JSONLFile)
- `IAIso::Core` — `Lifecycle` / `StepOutcome` (string constants),
  `Clock` with WallClock / ScriptedClock / ClosureClock, `PressureConfig`,
  `PressureEngine` with `MonitorMixin` thread safety, `BoundedExecution`
  with block-based `run` for automatic cleanup
- `IAIso::Consent` — `Algorithm` constants, hand-rolled JWT codec
  using OpenSSL stdlib for HS256 / RS256, constant-time signature
  comparison via `OpenSSL.fixed_length_secure_compare`. Issuer +
  Verifier with full claim-order control via Ruby's hash
  insertion-order preservation.
- `IAIso::Policy` — JSON-only policy loader, validator, all 4
  aggregators. Strict numeric typing rejects strings and Bools.
- `IAIso::Coordination` — `SharedPressureCoordinator`,
  `RedisCoordinator` with `UPDATE_AND_FETCH_SCRIPT` verbatim from
  `spec/coordinator/README.md §1.2`, byte-identical to all eight
  prior ports
- `IAIso::Middleware::{Anthropic,OpenAI,Gemini,Bedrock,Mistral,Cohere,LiteLLM}` —
  7 LLM provider adapters with duck-typed `Client` contracts
- `IAIso::Identity` — OIDC verifier with Okta / Auth0 / Azure AD
  presets. Uses `OpenSSL::ASN1` natively to construct
  SubjectPublicKeyInfo from JWK n/e fields — **no hand-rolled DER
  required**, unlike PHP and Swift.
- `IAIso::Metrics::PrometheusSink` and
  `IAIso::Observability::OtelSpanSink` with duck-typed contracts
- `IAIso::Conformance` — vector runner exposed to both the Minitest
  conformance suite and the CLI subcommand
- `iaiso` admin CLI (`exe/iaiso`) — policy, consent, audit,
  coordinator, conformance subcommands

**Notable Ruby wins over the prior eight ports**

1. **Hash insertion order preserved natively.** Ruby has guaranteed
   hash insertion order since 1.9. `JSON.generate({iss: ..., sub:
   ..., iat: ...})` emits keys in spec-mandated claim order
   automatically. **No `canonicalJSONDataOrdered` like Swift, no
   ordered-tuple list like Java.** Cross-language JWT byte
   compatibility was free.
2. **`OpenSSL::ASN1` for SubjectPublicKeyInfo** — building an RSA
   public key from JWK `n` / `e` is one ASN.1 sequence away. No
   hand-rolled DER like PHP / Swift.
3. **`MonitorMixin` is re-entrant by default**, so the engine doesn't
   deadlock when emit-callbacks land on the same thread. Skipped the
   "release lock around emit" dance that other ports needed.
4. **`OpenSSL.fixed_length_secure_compare`** for constant-time JWT
   signature comparison — built into stdlib.
5. **No NSNumber / Bool ambiguity.** Ruby distinguishes `Integer`,
   `Float`, `TrueClass`, `FalseClass` cleanly. Skipped the bug class
   that bit Java, Swift, and PHP.
6. **Block-based `BoundedExecution.run`** — reads exactly like
   `File.open`. The user pattern is
   `BoundedExecution.run(audit_sink: sink) { |exec| ... }` with
   automatic cleanup including the `execution.closed` event on
   exception.
7. **`autoload`** for lazy module loading — consumers who only need
   `IAIso::Core` don't pay for `IAIso::Identity` or
   `IAIso::Middleware::Cohere`.
8. **`Data.define`** (Ruby 3.2+) for true immutable value structs.
9. **Zero runtime dependencies** — `json`, `openssl`, `base64`,
   `securerandom`, `set`, `monitor` are all stdlib. Minitest is in
   stdlib. Rake is dev-only.

**Cross-language compatibility verified**

- A token loaded from `spec/consent/vectors.json` (signed by another
  reference SDK) verifies cleanly through this port's `Verifier` with
  matching subject and JTI.
- 67/67 conformance vectors pass, including all 23 consent vectors —
  scope matching, valid tokens, invalid tokens, and issue+verify
  roundtrips.
- RSA roundtrip test: 2048-bit key signs a token, JWKS loads via
  `set_jwks_from_bytes`, verification succeeds.

**Open items in this release**

- SIEM-vendor sinks (Splunk / Datadog / Loki / Elasticsearch ECS /
  Sumo / New Relic) deferred to 0.2.0. Use `JSONLFileSink` with a
  forwarder (Vector, Fluent Bit), or implement a sink in two methods
  — any object responding to `emit(event)` is a valid sink.
- YAML policies not supported. Convert YAML to JSON externally.

### Added — Swift reference port (SwiftPM, `iaiso-swift@0.1.0-draft`)

An eighth reference SDK has joined the seven prior ports. The Swift
implementation is a **SwiftPM package** with capabilities split into
ten library products (Audit, Core, Consent, Policy, Coordination,
Middleware, Identity, Metrics, Observability, Conformance) plus a
convenience `IAIso` aggregate and an `iaiso` admin CLI executable.
Targets **iOS 13+, macOS 10.15+, tvOS 13+, watchOS 6+, and Linux**.
~4,500 lines of source code; structural shape parallels the other
seven ports.

**⚠️ Validation note.** Every prior reference SDK was driven to 67/67
conformance vectors green through compile-test-fix iteration in the
build sandbox. **The Swift port was authored without a Swift toolchain
available** — Apple's Linux toolchain is hosted on
`download.swift.org`, which isn't on the build sandbox's network
allowlist. Every line was cross-checked by inspection against the
prior seven ports, and three substantive bugs were caught and fixed
that way (NSNumber/Bool ambiguity in `AnyJSON.from`, `EventsRunner`,
and `JWT.jsonEncode`; an ASN.1 DER ordering bug in `OidcVerifier`'s
`SubjectPublicKeyInfo` builder that would have prevented all OIDC RSA
verification). The conformance suite ships and is structurally
identical to the seven prior ports' suites. **Run `swift test` to
confirm 67/67 on your machine before depending on the port.**

**Module layout** (10 SwiftPM library products under `IAIso*` namespace)

- `IAIsoAudit` — `Event` envelope with hand-built canonical-JSON serialization
  (field order matches spec, alphabetical `data` key sorting, integer-valued
  floats emit as integers); `Sink` protocol; 5 sinks (Memory, Null, Stdout,
  Fanout, JSONLFile)
- `IAIsoCore` — `Lifecycle`, `StepOutcome` (string-raw enums), `Clock`
  protocol with WallClock/ScriptedClock/ClosureClock impls, `PressureConfig`,
  `PressureEngine`, `BoundedExecution` with `deinit` defensive close
- `IAIsoConsent` — `Algorithm` enum, hand-rolled JWT codec using **CryptoKit**
  for HMAC and **Security.framework `SecKey`** for RSA. Cross-platform via
  `swift-crypto` on Linux. Issuer + Verifier with full claim-order control
  via `canonicalJSONDataOrdered([(String, Any)])`.
- `IAIsoPolicy` — JSON-only policy loader, validator, all 4 aggregators.
  Strict numeric typing handles NSNumber-bridged-Bool gotcha that bit Java.
- `IAIsoCoordination` — `SharedPressureCoordinator`, `RedisCoordinator` with
  `UPDATE_AND_FETCH_SCRIPT` verbatim from `spec/coordinator/README.md §1.2`,
  byte-identical to all prior ports
- `IAIsoMiddleware` — single target with sub-folders for 7 providers
  (Anthropic, OpenAI, Gemini, Bedrock, Mistral, Cohere, LiteLLM). Provider
  types are namespaced via Swift's `enum` namespace pattern (e.g.
  `Anthropic.Client`, `Anthropic.BoundedClient`).
- `IAIsoIdentity` — OIDC verifier with Okta / Auth0 / Azure AD presets.
  Hand-built ASN.1 DER `SubjectPublicKeyInfo` PEM construction from JWK
  `n`/`e` fields → `SecKey` for `openssl_verify`-style verification.
- `IAIsoMetrics` — `PrometheusSink` with structural Counter/Gauge/Histogram
  protocols
- `IAIsoObservability` — `OtelSpanSink` with structural `Tracer`/`Span`
  protocols
- `IAIsoConformance` — vector runner; XCTest suite that loads the spec via
  `IAISO_SPEC_DIR` env var or relative path
- `IAIsoCLI` — admin CLI executable

**Notable Swift-idiomatic decisions**

- **No `Builder` pattern.** Swift's keyword-argument initializers + default
  values give the same call-site ergonomics as Java/PHP/C# builders without
  the boilerplate. `PressureConfig(escalationThreshold: 0.7,
  releaseThreshold: 0.85)` reads cleanly.
- **`@unchecked Sendable`** on classes with manual NSLock synchronization.
  This is correct Swift 5.9+ for thread-safe classes the compiler can't
  auto-prove safe.
- **Native enums for wire-format strings.** `Lifecycle`,
  `StepOutcome`, `Algorithm`, `CoordinatorLifecycle` all back to `String`
  raw values that match the spec wire format — `Lifecycle.running.rawValue
  == "running"` for free.
- **`deinit` on `BoundedExecution`** as a defensive `closeWith(errored:
  false)` so even users who forget to `close()` still get the
  `execution.closed` event. ARC fires deinit deterministically.
- **CryptoKit on Apple, swift-crypto on Linux** via `@_exported import`
  conditional compilation. iOS / macOS / tvOS / watchOS use the system
  framework — no dependency. Linux consumers add `swift-crypto` to their
  Package.swift.
- **JSON-only policies.** Swift has no built-in YAML parser; pulling
  `Yams` would compromise the dependency-light pitch. Convert YAML to
  JSON externally if needed.
- **`AnyJSON` enum** as the value type for event data and JSON parsing,
  with `ExpressibleBy*Literal` conformances for ergonomic construction.
  The `from(_:)` factory carefully handles NSNumber/Bool disambiguation
  on Apple platforms via `objCType`.

**Open items in this release**

- Conformance suite has not been driven through a real toolchain by
  Anthropic; users must run `swift test` to confirm.
- SIEM-vendor sinks (Splunk / Datadog / Loki / Elasticsearch ECS / Sumo /
  New Relic) deferred to 0.2.0. Users with immediate needs can implement
  a sink in three lines (the `Sink` protocol is just `func emit(_ event:
  Event)`) or use `JSONLFileSink` with a forwarder.
- Linux RSA signing currently throws — `Security.framework` is Apple-only.
  Use `swift-crypto`'s `_RSA.Signing` module on Linux when needed.
  HMAC-SHA256 (HS256) works on every platform.

### Added — PHP reference port (Composer package, `iaiso/iaiso@0.1.0`)

A seventh reference SDK has joined the Python, Node, Go, Rust, Java,
and C# ports. The PHP implementation is a single Composer package with
capabilities cleanly separated into sub-namespaces under `IAIso\`, so
consumers `use` only what they need. Full feature parity with the
runtime layer of the other reference SDKs: **53 unit tests + 67
conformance vectors** all passing on PHP 8.2+.

**Sub-namespace layout** (single `iaiso/iaiso` package, 126 classes)

- `IAIso\Core` — pressure engine + `BoundedExecution` facade
- `IAIso\Consent` — JWT issuer/verifier (HS256/RS256), revocation,
  execution binding. Hand-rolled JWT using `hash_hmac` and
  `openssl_sign`/`openssl_verify` — **no JWT library dependency**.
- `IAIso\Audit` — event envelope (with explicit field-order
  serialization guaranteeing the spec-mandated key order) and base
  sinks (memory, null, stdout, fanout, JSONL)
- `IAIso\Policy` — JSON loader, validator, all 4 aggregators
- `IAIso\Coordination` — in-memory + Redis-backed coordinator. Lua
  script verbatim from `spec/coordinator/README.md §1.2`,
  interoperable with the Python, Node, Go, Rust, Java, and C# references.
- `IAIso\Middleware\{Anthropic,OpenAi,Gemini,Bedrock,Mistral,Cohere,LiteLlm}` —
  7 LLM provider adapters in PSR-4 sub-namespaces
- `IAIso\Identity` — OIDC verifier with Okta / Auth0 / Azure AD
  presets, scope mapping, and `issueFromOidc`. Hand-rolled ASN.1 DER
  encoding to build an RSA `SubjectPublicKeyInfo` PEM from a JWK's
  base64url-encoded `n` and `e` fields, then verified with
  `openssl_verify()`.
- `IAIso\Metrics` — Prometheus sink (structural interfaces)
- `IAIso\Observability` — OpenTelemetry tracing sink (structural)
- `IAIso\Conformance` — vector runner exposed to both the PHPUnit
  conformance suite and the CLI subcommand
- `IAIso\Cli` — admin CLI (`bin/iaiso` launcher, available as
  `vendor/bin/iaiso` after Composer install)

**Dependency hygiene**

The package has **zero direct runtime dependencies**. PHP 8.2+ ships
`ext-json`, `ext-openssl`, `ext-hash`, `ext-mbstring` — all built-in
modules — and that's all we need. JWT signing/verification is
implemented in-house. Every other integration (Redis client,
Prometheus library, OpenTelemetry SDK, LLM provider SDKs, HTTP clients)
is wired through **structural interfaces** that users satisfy with
thin adapters around whichever library they already use. PHPUnit is
dev-only.

**PHP-idiomatic touches**

- Native PHP 8 backed enums for `Lifecycle`, `StepOutcome`,
  `Algorithm`, `CoordinatorLifecycle` — backed by string with the
  lowercase wire value, so `Lifecycle::Running->value === "running"`
  for free across the entire codebase.
- `readonly` properties + constructor promotion throughout — idiomatic
  PHP 8.1+, immutable by default. Builders for the aggregate types.
- `__destruct` on `BoundedExecution` as a defensive `closeWith(false)`
  so users who forget to `close()` still get the `execution.closed`
  event. PHP's GC fires `__destruct` reliably for normal object
  lifetimes.
- `array_is_list()` (PHP 8.1+) for list-vs-map disambiguation in the
  policy validator and Event JSON encoder. PHP arrays double as both,
  so this is the idiomatic way to reject a JSON array as a top-level
  policy or to render lists vs maps correctly in audit JSON.
- PSR-4 strict, one class per file. 126 classes load via Composer's
  optimized autoloader.

**Open items in this release**

- SIEM-vendor sinks (Splunk / Datadog / Loki / Elasticsearch ECS /
  Sumo / New Relic) are not yet shipped in the PHP port. Users with
  immediate needs can implement a sink in two lines (the `Sink`
  interface is just `public function emit(Event $event): void`) or
  use `JsonlFileSink` with a forwarder.
- PHP has no built-in YAML parser. The PHP port supports JSON-only
  policies; convert YAML externally if needed.

### Added — C# / .NET reference port (multi-project solution, `Iaiso.*@0.1.0`)

A sixth reference SDK has joined the Python, Node, Go, Rust, and Java
ports. The C# implementation is a .NET 8 (LTS) multi-project solution
with 11 source projects so users add only the assemblies they need.
Full feature parity with the runtime layer of the other reference SDKs:
**50 unit tests + 67 conformance vectors** all passing.

**Project layout**

- `Iaiso.Core` — pressure engine + `BoundedExecution` facade
- `Iaiso.Consent` — JWT issuer/verifier (HS256/RS256), revocation,
  execution binding. Hand-rolled JWT using `System.Security.Cryptography`
  primitives — **no JWT library dependency**.
- `Iaiso.Audit` — event envelope (with explicit field-order
  serialization guaranteeing the spec-mandated key order) and base
  sinks (memory, null, stdout, fanout, JSONL)
- `Iaiso.Policy` — JSON loader, validator, all 4 aggregators
- `Iaiso.Coordination` — in-memory + Redis-backed coordinator. Lua
  script verbatim from `spec/coordinator/README.md §1.2`,
  interoperable with the Python, Node, Go, Rust, and Java references.
- `Iaiso.Middleware` — 7 LLM provider adapters in sub-namespaces
  (`Iaiso.Middleware.Anthropic`, `Iaiso.Middleware.OpenAi`,
  `Iaiso.Middleware.Gemini`, `Iaiso.Middleware.Bedrock` with both
  Converse and InvokeModel, `Iaiso.Middleware.Mistral`,
  `Iaiso.Middleware.Cohere`, `Iaiso.Middleware.LiteLlm`)
- `Iaiso.Identity` — OIDC verifier with Okta / Auth0 / Azure AD
  presets, scope mapping, and `IssueFromOidc`
- `Iaiso.Metrics` — Prometheus sink (structural interfaces)
- `Iaiso.Observability` — OpenTelemetry tracing sink (structural)
- `Iaiso.Conformance` — vector runner exposed to both the in-tree
  test suite and the CLI subcommand
- `Iaiso.Cli` — admin CLI (`iaiso` command, ships as a regular .NET
  `Exe` project that publishes to a single-file binary)

**Dependency hygiene**

The solution has **zero direct runtime dependencies**. JSON via
`System.Text.Json` (built-in), crypto via `System.Security.Cryptography`
(built-in), JWT signing/verification implemented in-house. Every other
integration (Redis client, Prometheus library, OpenTelemetry SDK, LLM
provider SDKs, HTTP clients) is wired through **structural interfaces**
that users satisfy with thin adapters around whichever library they
already use. This is the .NET-idiomatic equivalent of Node's
peer-dependency pattern, Go's structural-interface pattern, Rust's
structural-trait pattern, and Java's structural-interface pattern — the
SDK itself stays small and dependency-free while supporting every major
surrounding ecosystem.

**Testing without xUnit**

The test project (`tests/Iaiso.Tests/`) is a regular .NET `Exe` that
contains its own tiny in-tree test runner: reflection-based discovery
of methods named `Test*` on classes ending in `Tests`. This avoids any
external test framework (xUnit / NUnit / MSTest) dependency and lets
the suite run identically in restricted environments. `dotnet test`
runs it via a thin `<TestSuite>` MSBuild target; `dotnet run` against
the project works directly.

**Open items in this release**

- SIEM-vendor sinks (Splunk / Datadog / Loki / Elasticsearch ECS /
  Sumo / New Relic) are not yet shipped in the C# port. Users with
  immediate needs can implement a sink in two methods (the `ISink`
  interface is just `void Emit(Event @event)`) or use `JsonlFileSink`
  with a forwarder.
- `System.Text.Json` doesn't ship with YAML support. The C# port
  supports JSON-only policies; convert YAML externally if needed.

### Added — Java reference port (Maven workspace, `io.iaiso:iaiso-*@0.1.0`)

A fifth reference SDK has joined the Python, Node, Go, and Rust ports.
The Java implementation is a Maven multi-module project with 11 modules
so users add only the artifacts they need. Full feature parity with the
runtime layer of the other reference SDKs: **50 unit tests + 67
conformance vectors** all passing on JDK 17+.

**Module layout**

- `iaiso-core` — pressure engine + `BoundedExecution` facade
- `iaiso-consent` — JWT issuer/verifier (HS256/RS256), revocation,
  execution binding. Hand-rolled JWT using `javax.crypto.Mac` and
  `java.security.Signature` — **no JWT library dependency**.
- `iaiso-audit` — event envelope (with explicit field-order
  serialization guaranteeing the spec-mandated key order) and base
  sinks (memory, null, stdout, fanout, JSONL)
- `iaiso-policy` — JSON loader, validator, all 4 aggregators
- `iaiso-coordination` — in-memory + Redis-backed coordinator. Lua
  script verbatim from `spec/coordinator/README.md §1.2`,
  interoperable with the Python, Node, Go, and Rust references.
- `iaiso-middleware` — 7 LLM provider adapters (Anthropic, OpenAI /
  OpenAI-compatible, Gemini, Bedrock with both Converse and
  InvokeModel, Mistral, Cohere, LiteLLM proxy-pattern helper)
- `iaiso-identity` — OIDC verifier with Okta / Auth0 / Azure AD
  presets, scope mapping, and `issueFromOidc`
- `iaiso-metrics` — Prometheus sink (structural interfaces)
- `iaiso-observability` — OpenTelemetry tracing sink (structural)
- `iaiso-conformance` — vector runner exposed to both the in-tree
  test suite and the CLI subcommand
- `iaiso-cli` — admin CLI (`iaiso` command)

**Dependency hygiene**

The workspace's only required runtime dependency is **Gson** for JSON
parsing. Every other integration (Redis client, Prometheus library,
OpenTelemetry SDK, LLM provider SDKs, HTTP clients) is wired through
**structural interfaces** that users satisfy with thin adapters around
whichever library they already use. JWT signing/verification is
implemented in-house using only the JDK's built-in crypto. This is the
Java-idiomatic equivalent of Node's peer-dependency pattern, Go's
structural-interface pattern, and Rust's structural-trait pattern — the
SDK itself stays small and JAR-hell-free while supporting every major
surrounding ecosystem.

**Open items in this release**

- SIEM-vendor sinks (Splunk / Datadog / Loki / Elasticsearch ECS /
  Sumo / New Relic) are not yet shipped in the Java port. Users with
  immediate needs can implement a sink in two methods (the `Sink`
  interface is just `void emit(Event event)`) or use `JsonlFileSink`
  with a forwarder.
- Java has no built-in YAML parser. The Java port supports JSON-only
  policies; convert YAML externally if needed.

### Added — Rust reference port (Cargo workspace, `iaiso-*@0.1.0`)

A fourth reference SDK has joined the Python, Node, and Go ports. The
Rust implementation is a Cargo workspace with 13 member crates so
users add only what they need. Full feature parity with the runtime
layer of the Python, Node, and Go references: **47 unit tests + 1
doc test + 67 conformance vectors** all passing.

**Workspace layout**

- `crates/core` — pressure engine + `BoundedExecution` facade
- `crates/consent` — JWT issuer/verifier (HS256/RS256), revocation,
  execution binding
- `crates/audit` — event envelope (with custom `serde::Serialize`
  guaranteeing the spec-mandated key order) and base sinks
  (memory, null, stdout, fanout, JSONL)
- `crates/policy` — JSON + YAML loader, validator, all 4 aggregators
- `crates/coordination` — in-memory + Redis-backed coordinator. Lua
  script verbatim from `spec/coordinator/README.md §1.2`,
  interoperable with the Python, Node, and Go references.
- `crates/middleware` — 7 LLM provider adapters (Anthropic, OpenAI /
  OpenAI-compatible, Gemini, Bedrock with both Converse and
  InvokeModel, Mistral, Cohere, LiteLLM proxy-pattern helper)
- `crates/identity` — OIDC verifier with Okta / Auth0 / Azure AD
  presets, scope mapping, and `issue_from_oidc`
- `crates/metrics` — Prometheus sink (structural traits)
- `crates/observability` — OpenTelemetry tracing sink (structural)
- `crates/conformance` — vector runner exposed to both the in-tree
  test suite and the standalone binary
- `crates/cli` — admin CLI implementation
- `cmd/iaiso` + `cmd/iaiso-conformance` — binary entry points

**Dependency hygiene**

The workspace's only required dependencies are `serde`, `serde_json`,
`serde_yaml`, `thiserror`, `parking_lot`, `chrono`, `jsonwebtoken`,
and `base64`. Every other integration (Redis client, Prometheus
library, OpenTelemetry SDK, LLM provider SDKs) is wired through
**structural traits** that users satisfy with thin adapters around
whichever crate they already use. This is the Rust-idiomatic
equivalent of Node's peer-dependency pattern and Go's structural-
interface pattern — the SDK itself stays small and import-graph-clean
while supporting every major surrounding ecosystem.

**Open items in this release**

- SIEM-vendor sinks (Splunk / Datadog / Loki / Elasticsearch ECS /
  Sumo / New Relic) are scaffolded behind Cargo features but not yet
  implemented in this initial release. The base sinks plus the
  webhook/jsonl primitives cover most needs; SIEM sink bodies will
  follow in `0.2.0`.
- The crate is HTTP-free; users supply HTTP clients (e.g. `reqwest`)
  for OIDC JWKS fetching and SIEM forwarding.

### Added — Go reference port `github.com/iaiso/iaiso-go@v0.1.0`

A third reference SDK has joined the Python and Node ports. The Go
implementation is structurally complete on day one: full feature
parity with the Python and Node references, **48 unit tests + 67
conformance vectors** all passing.

**Coverage**

- Pressure engine with full lifecycle semantics, BoundedExecution
  facade with both `Run(opts, fn)` callback and `Start(opts) +
  Close()` patterns.
- Consent tokens (HS256 / RS256) via `github.com/golang-jwt/jwt/v5`,
  with `RevocationList` and execution-binding checks.
- Audit envelope with deterministic JSON key order, plus 6 base sinks
  (memory, null, stdout, fanout, JSONL, webhook) and 6 SIEM sinks in
  their own subpackages: `audit/sinks/{splunk,datadog,loki,elastic,sumo,newrelic}`.
- Policy-as-code loader supporting JSON and YAML (via
  `github.com/goccy/go-yaml`).
- Coordination: in-memory `SharedPressureCoordinator` and
  Redis-backed `RedisCoordinator` (interoperable with the Python and
  Node references via the normative Lua script in
  `spec/coordinator/README.md §1.2`).
- LLM middleware: 7 provider adapters under `iaiso/middleware/`:
  Anthropic, OpenAI / OpenAI-compatible, Google Gemini, AWS Bedrock
  (Converse + InvokeModel), Mistral, Cohere, and LiteLLM proxy-pattern
  helper.
- OIDC identity: JWKS verifier with Okta / Auth0 / Azure AD presets,
  scope mapping, and an `IssueFromOIDC` flow that mints IAIso consent
  scopes from validated OIDC identities.
- Metrics: `PrometheusSink` (structurally typed against any
  Prometheus client library).
- Observability: `OtelSpanSink` (structurally typed against the OTel
  trace API).
- Admin CLI: `iaiso` binary with `policy validate/template`,
  `consent issue/verify`, `audit tail/stats`, `coordinator demo`, and
  `conformance` subcommands; `iaiso-conformance` as a standalone
  binary entry.

**Dependency hygiene**

The Go module has only two transitive dependencies — the JWT library
and the YAML parser. Every other integration (Redis client,
Prometheus library, OpenTelemetry SDK, LLM provider SDKs) is wired
in through **structural interfaces** that users satisfy with thin
adapters around whichever library they already use. This is the
Go-idiomatic equivalent of Node's peer-dependency pattern: the SDK
itself stays small and import-graph-clean while supporting every
major surrounding ecosystem.

### Added — Node reference port `@iaiso/core@0.3.0`

The Node port now reaches feature parity with the Python SDK plus a
dedicated admin CLI. Full test suite: **171 tests** (104 unit + 67
conformance). Every additional capability rides on a peer dependency —
users install only what they use.

**New LLM middleware**

- `GeminiBoundedModel` — wraps `@google/generative-ai`. Accounts
  `response.usageMetadata` tokens and counts `functionCall` parts.
- `BedrockBoundedClient` — wraps
  `@aws-sdk/client-bedrock-runtime`. Supports both the `Converse`
  API and `InvokeModel`.
- `MistralBoundedClient` — wraps `@mistralai/mistralai`. Reads
  `response.usage.totalTokens` with fallback to prompt+completion.
- `CohereBoundedClient` — wraps `cohere-ai`. Reads tokens from
  `meta.billedUnits` / `meta.billed_units` (both shapes supported).
- `createLiteLLMClient(OpenAICtor, opts)` — typed factory for the
  LiteLLM-proxy pattern; returns an OpenAI SDK client pointed at the
  proxy. Wrap with `OpenAIBoundedClient` for accounting.

**New SIEM sinks**

- `ElasticECSSink` — maps events to Elastic Common Schema fields
  (`@timestamp`, `event.kind`, `event.dataset`, `event.action`, `labels`,
  `iaiso.*`). Supports both Basic auth and `ApiKey` auth.
- `SumoLogicSink` — POSTs to a Sumo Logic HTTP Source URL with
  `X-Sumo-Name` / `X-Sumo-Category` / `X-Sumo-Host` headers.
- `NewRelicLogsSink` — POSTs to `log-api.newrelic.com` with `Api-Key`
  header and `iaiso.*`-prefixed attributes.

Each SIEM sink exports a pure payload function
(`elasticECSPayload`, `sumoLogicPayload`, `newRelicLogsPayload`) for
wire-format validation without network I/O.

**OIDC identity integration** (`src/identity/`)

- `OIDCVerifier` over `jose.createRemoteJWKSet` with automatic
  discovery-document fetch and JWKS caching (default 10 minutes).
- Provider presets: `oktaConfig`, `auth0Config`, `azureAdConfig` (v1 / v2).
- `deriveScopes` with pluggable mapping: direct claims (`scp`, `scope`,
  `permissions`), group → scope mapping, and always-grant scopes.
- `issueFromOidc` high-level flow: verify an OIDC token → mint an
  IAIso-signed `ConsentScope` with scopes derived from OIDC claims.

**Metrics and tracing**

- `PrometheusMetricsSink` — audit sink that drives `prom-client`:
  `iaiso_events_total{kind}`, `iaiso_escalations_total`,
  `iaiso_releases_total`, `iaiso_pressure{execution_id}`,
  `iaiso_step_delta` histogram.
- `OtelSpanSink` — opens one OpenTelemetry span per execution, attaches
  every audit event as a span event, mirrors `pressure` / `escalated` /
  `released` as span attributes, closes on `execution.closed`.

**Admin CLI** (`iaiso`)

New `iaiso` bin alongside `iaiso-conformance`. Subcommands:

- `iaiso policy validate <file>` — check a policy file for errors.
- `iaiso policy template <file>` — write a blank policy template.
- `iaiso consent issue <sub> <scope,...> [ttl]` — issue an HS256 token
  (requires `IAISO_HS256_SECRET`).
- `iaiso consent verify <token>` — verify + print the decoded scope.
- `iaiso audit tail <jsonl-file>` — pretty-print audit events.
- `iaiso audit stats <jsonl-file>` — count events by kind, distinct
  executions.
- `iaiso coordinator demo` — in-memory coordinator smoke test with
  callbacks.
- `iaiso conformance <spec-dir>` — alias for `iaiso-conformance`.

Prior Node releases (`0.2.0`: middleware + Redis + basic SIEM;
`0.1.0`: core engine + consent + audit) remain as described below.

### Added — Node reference port `@iaiso/core@0.2.0`

- LLM middleware: `AnthropicBoundedClient`, `OpenAIBoundedClient`,
  `IaisoCallbackHandler` (LangChain).
- Cross-execution coordination: `SharedPressureCoordinator` (in-memory)
  and `RedisCoordinator` (interoperable with the Python reference via
  the normative Lua script in `spec/coordinator/README.md §1.2`).
- SIEM sinks: `SplunkHECSink`, `DatadogLogsSink`, `LokiSink`, with
  exported payload-shape functions.
- YAML policy loader: `loadPolicyYaml` + `parsePolicyYaml`.

### Added — Node reference port `@iaiso/core@0.1.0`

- Pressure engine, consent tokens (HS256/RS256), audit envelope with 5
  base sinks (stdout, JSONL, webhook, fanout, memory), policy-as-code
  loader (JSON), `BoundedExecution` facade, conformance runner + CLI.

All additional dependencies are peer dependencies. Requires Node.js ≥ 20.

## [0.2.0] — 2026-04-24

This release extracts IAIso's contracts from implicit-in-Python-code
into a **normative specification** at `spec/`, with machine-checkable
JSON Schemas and 67 executable test vectors. The Python package is
now the reference implementation of that specification rather than
the specification itself.

This is the foundation for ports to other languages (Node, Go, Rust,
Java). See `docs/CONFORMANCE.md` for the porting workflow.

### Added

**Specification**
- `spec/pressure/` — normative pressure model with 20 hand-computed
  test vectors covering threshold boundaries, lock state, clamping,
  dissipation, and full trajectories.
- `spec/consent/` — normative JWT + scope grammar specification with
  `claims.schema.json` (JSON Schema 2020-12) and 23 test vectors
  (12 scope-match + 4 valid tokens + 4 invalid tokens + 2 roundtrips
  + edge cases).
- `spec/events/` — normative event envelope with `envelope.schema.json`
  and per-kind `payloads.schema.json`, plus 7 event-stream vectors
  that lock in emission order (step → escalation; step → release →
  locked).
- `spec/policy/` — normative policy file format with
  `policy.schema.json` and 17 vectors (8 valid + 9 invalid, including
  forward-compatibility guarantees for unknown keys).
- `spec/coordinator/` — Redis keyspace specification (atomic Lua
  update script + keyspace layout) and a DRAFT gRPC wire format
  (`wire.proto`) for a future sidecar.
- `spec/VERSION` — pinned at `1.0`.

**Conformance infrastructure**
- `iaiso.conformance` package with runners for pressure, consent,
  events, and policy vectors.
- `iaiso.conformance.ScriptedClock` for deterministic time in
  engine tests.
- `python -m iaiso.conformance spec/` CLI (exit code 0 iff all
  vectors pass; `--section`, `--verbose` flags).
- `tests/test_conformance.py` runs every vector as an individual
  parametrized pytest case, so CI output identifies the exact failing
  vector.

**Documentation**
- `docs/CONFORMANCE.md` — step-by-step guide for building an
  IAIso-conformant implementation in a new language.
- `spec/README.md` — spec index, versioning policy, tolerance
  (`1e-9` absolute for floats).

### Changed

- `iaiso.policy._validate` now enforces cross-field rules
  (release > escalation in both pressure and coordinator sections),
  scope-grammar validation on `consent.required_scopes`, and
  forward-compatible handling of unknown keys (warned but not
  rejected, per `spec/policy/README.md §2`).
- `docs/spec/events.md`, `docs/spec/consent.md`,
  `docs/spec/pressure-model.md` are now thin redirect stubs pointing
  to `spec/*/README.md`. The prose content moved to `spec/`.
- `README.md` now links to the `spec/` directory as the normative
  source.

### Notes for implementers porting to other languages

- Float tolerance is `1e-9` absolute. Bit-exact IEEE-754 parity is
  not required across languages.
- `spec/VERSION` gates spec-version compatibility. Pin your port to
  a specific version.
- MINOR spec bumps may add vectors; existing vectors are never edited.
  Your port's CI should pass all vectors for its pinned spec version.



## [0.1.0] — 2026-04-23

Initial public SDK release of the IAIso framework's reference
implementation. Every feature in this release is backed by tests; the
SDK ships as the Python reference runtime of the framework specified
in [`../../vision/`](../../vision/).

### Added

**Core execution**
- `PressureEngine`: deterministic pressure accumulation with
  configurable coefficients, escalation threshold, and release
  threshold. Deterministic for given inputs; all coefficients are
  exposed rather than implicit.
- `BoundedExecution`: lifecycle-managed execution wrapper with
  post-release locking, scope gating, and audit emission on every
  transition.
- `ConsentScope` / `ConsentIssuer` / `ConsentVerifier`: HS256 and
  RS256 JWT-based signed consent tokens with scope matching, TTL,
  unique jti for revocation, and revocation list support.
- `ScopeRevocationList` / `RedisRevocationList`: in-memory and Redis
  backends for real-time token invalidation.

**Audit infrastructure**
- Versioned audit event schema (see `docs/spec/events.md`).
- Sinks: `StdoutSink`, `JSONLSink`, `MemorySink`, `NullSink`,
  `FanoutSink`, `WebhookSink`.
- SIEM sinks: Splunk HEC, Datadog Logs, Elastic Common Schema, Sumo
  Logic HTTP Source, New Relic Logs, Grafana Loki.

**Middleware**
- `AnthropicBoundedClient`, `AnthropicAsyncBoundedClient`.
- `OpenAIBoundedClient`, `AsyncOpenAIBoundedClient`. Compatible with
  any OpenAI-SDK-wire-format provider (Azure OpenAI, Groq, self-hosted
  vLLM, Ollama, TGI, SGLang, LocalAI) via `base_url` override.
- `BoundedLLMChain` wrapper for LangChain.
- `BoundedLiteLLM` for LiteLLM router.
- `GeminiBoundedModel` for google-generativeai / Vertex AI.
- `BedrockBoundedClient` for AWS Bedrock Runtime (both Converse API
  and invoke_model).
- `MistralBoundedClient`, `CohereBoundedClient`.

**Distributed coordination**
- `SharedPressureCoordinator` for single-process fleet aggregation
  with pluggable aggregators (sum, mean, max, weighted sum).
- `RedisCoordinator` for multi-process fleets with atomic Lua-script
  updates.

**Operational**
- `iaiso.metrics`: Prometheus and OpenTelemetry exporters, plus
  in-memory sink with bundled Prometheus exposition format.
- `iaiso.observability.tracing`: OTel span wrapping for
  `BoundedExecution` with child spans per step.
- `iaiso.policy`: YAML/JSON configuration loader with inline schema
  validation; template generator.
- `iaiso.cli`: `iaiso policy validate`, `iaiso policy template`,
  `iaiso consent issue`, `iaiso consent verify`, `iaiso audit tail`,
  `iaiso audit stats`, `iaiso coordinator demo`.
- `iaiso.reliability`: `CircuitBreaker` and `retry_after_seconds()`.
- `iaiso.identity`: OIDC access-token verification via JWKS with
  scope enrichment; Okta, Auth0, and Azure AD presets.

**Calibration and evaluation**
- `iaiso.calibration`: grid search over pressure coefficients
  against recorded trajectories with configurable objective.
- `iaiso.evaluation`: deterministic test scenarios (token bloat,
  tool spam, planning explosion, mixed).
- `scripts/record_swebench.py`, `scripts/record_gaia.py`,
  `scripts/record_generic.py`: trajectory recorders for standard
  benchmarks. Users run these against real APIs; infrastructure
  ships with the library, empirical results do not.

**Deployment**
- `deploy/docker/Dockerfile`: multi-stage production image with
  non-root user and read-only root filesystem.
- `deploy/helm/`: Helm chart with ServiceMonitor, PodDisruptionBudget,
  restricted PodSecurityContext, and ConfigMap for policy.
- `deploy/terraform/`: Terraform module wrapping the Helm chart.

**Benchmarks**
- `iaiso.bench.microbench`: single-process throughput benchmark for
  core primitives. See `bench/README.md` for what the numbers do
  and don't mean.

**Documentation**
- `docs/THREAT_MODEL.md`: adversaries, assets, trust boundaries, and
  mitigation mapping.
- `docs/BACKWARDS_COMPATIBILITY.md`: versioning and deprecation
  policy.
- `docs/CONTRIBUTING.md`: how to propose changes.
- `docs/known-limitations.md`: SDK scope and how it composes with
  adjacent safety layers.
- `docs/graceful-degradation.md`: playbook for downstream outages.
- `docs/shadow-canary-mode.md`: recommended rollout pattern.
- `docs/self-hosted.md`: integrating with self-hosted LLM backends.

### Security

- All SIEM sinks default to TLS verification enabled.
- Consent tokens use signed JWTs; HS256 and RS256 supported.
- Helm chart enforces restricted PodSecurityContext by default.
- OIDC verifier requires asymmetric algorithms (RS256/ES256);
  symmetric algorithms (HS256) are explicitly rejected for IdP
  verification.

### Known limitations

See `docs/known-limitations.md` for the full list. Key items:

- Performance numbers published are single-process microbenchmarks,
  not production-scale.
- SIEM sinks are wire-format-correct but have not been
  end-to-end-tested against every vendor's live endpoints.
- Redis coordinator callbacks fire per-process, not globally
  (documented behavior, not a bug).
- No hardware-level enforcement. IAIso is a software library; it
  cannot stop a compromised process from making direct API calls
  that bypass the library.

[Unreleased]: https://github.com/your-org/iaiso/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/your-org/iaiso/releases/tag/v0.1.0
