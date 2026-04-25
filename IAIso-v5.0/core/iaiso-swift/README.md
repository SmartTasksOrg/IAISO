# iaiso-swift

**Swift reference SDK for the IAIso bounded-agent-execution framework.**

IAIso adds pressure-based rate limiting, scope-based authorization, and
structured audit logging to LLM agent loops. This is the Swift
implementation, conformant to **IAIso spec 1.0**.

> Targets **iOS 13+**, **macOS 10.15+**, **tvOS 13+**, **watchOS 6+**, and **Linux**.
> Single SwiftPM package with capabilities split into per-target library
> products. Wire-format compatible with the [Python](../iaiso-python/),
> [Node](../iaiso-node/), [Go](../iaiso-go/), [Rust](../iaiso-rust/),
> [Java](../iaiso-java/), [C#](../iaiso-csharp/), and
> [PHP](../iaiso-php/) reference SDKs — same audit events, same JWTs,
> same Redis Lua script.

## ⚠️ Validation status — `0.1.0-draft`

Every prior reference SDK was driven to **67/67 conformance vectors green**
through compile-test-fix iteration in the build sandbox. The Swift port
was authored without an available Swift toolchain (Apple's Linux
toolchain is hosted on `download.swift.org`, which isn't on the build
sandbox's network allowlist), so **the conformance suite has NOT been
run against this port**. Every line of code was cross-checked against
the seven prior ports' equivalent logic, but the binary truth of "67/67"
needs to come from your `swift test` run.

**To validate before you depend on this:**

```bash
git clone <iaiso-merged>
cd core/iaiso-swift
swift test                                      # builds + runs unit tests + conformance suite
```

If a vector fails, file an issue with the `[section] name: message`
line — those messages were designed to be diagnostic, and the same
patterns are now battle-tested across the seven prior ports, so the
fix is usually obvious.

## Workspace layout

```
iaiso-swift/
├── Package.swift                 # SwiftPM manifest, 10 library products + iaiso CLI exe
├── README.md, LICENSE, .gitignore
├── spec/                         # normative spec + 67 conformance vectors
├── Sources/
│   ├── IAIsoAudit/               # event envelope + base sinks
│   ├── IAIsoCore/                # pressure engine + BoundedExecution
│   ├── IAIsoConsent/             # JWT issuer/verifier (HS256/RS256)
│   ├── IAIsoPolicy/              # JSON policy loader
│   ├── IAIsoCoordination/        # in-memory + Redis coordinator
│   ├── IAIsoMiddleware/          # 7 LLM provider wrappers (enum namespaces)
│   ├── IAIsoIdentity/            # OIDC verifier + scope mapping
│   ├── IAIsoMetrics/             # Prometheus sink (structural)
│   ├── IAIsoObservability/       # OpenTelemetry sink (structural)
│   ├── IAIsoConformance/         # vector runner
│   └── IAIsoCLI/                 # admin CLI executable target
└── Tests/                        # XCTest, one suite per target
```

## Install

In your `Package.swift`:

```swift
dependencies: [
    .package(url: "https://github.com/SmartTasksOrg/IAISO.git", from: "0.1.0"),
],
targets: [
    .target(
        name: "MyApp",
        dependencies: [
            .product(name: "IAIso", package: "IAISO"),
            // or, à la carte:
            // .product(name: "IAIsoCore", package: "IAISO"),
            // .product(name: "IAIsoConsent", package: "IAISO"),
        ]
    ),
]
```

The `IAIso` convenience product re-exports
`IAIsoAudit + IAIsoCore + IAIsoConsent + IAIsoPolicy + IAIsoCoordination`.
For tighter binaries, depend on individual targets only.

### Linux

On Linux, add `swift-crypto` for the HMAC implementation. CryptoKit is
Apple-only; `swift-crypto` provides the same API:

```swift
.package(url: "https://github.com/apple/swift-crypto.git", from: "3.0.0"),
```

The `IAIsoConsent` module conditionally imports `Crypto` on platforms
that don't have CryptoKit. RSA verification on Linux currently requires
swift-crypto's `_RSA.Signing` module (planned for 0.2.0); HS256 works
out of the box.

## Quick start

```swift
import IAIso

let sink = MemorySink()
try BoundedExecution.run(
    BoundedExecution.Options(auditSink: sink)
) { exec in
    let outcome = exec.recordToolCall("search", tokens: 500)
    if outcome == .escalated {
        // Layer 4: request human review per the escalation template
    }
}
```

## LLM middleware

Each provider is namespaced via Swift's `enum` namespace pattern:

```swift
import IAIsoCore
import IAIsoMiddleware

class MyAnthropicAdapter: Anthropic.Client {
    // Wraps your favourite Anthropic SDK or a plain URLSession call.
    func messagesCreate(_ params: [String: Any]) throws -> Anthropic.Response {
        // ... call upstream, map into Anthropic.Response
    }
}

let bounded = Anthropic.BoundedClient(
    raw: MyAnthropicAdapter(),
    execution: exec,
    options: .defaults
)
let resp = try bounded.messagesCreate(params)
```

Adapters: `Anthropic`, `OpenAI` (works with any OpenAI-compatible
endpoint — Azure OpenAI, vLLM, TGI, LiteLLM proxy, Together, Groq),
`Gemini`, `Bedrock` (Converse + InvokeModel), `Mistral`, `Cohere`,
and `LiteLLM` (proxy-pattern helper).

The structural `Client` protocol approach keeps the SDK free of any
specific provider package — you bring your own HTTP client.

## Distributed coordination

In-memory:

```swift
import IAIsoCoordination

let coord = try SharedPressureCoordinator(
    coordinatorId: "fleet",
    escalationThreshold: 5.0,
    releaseThreshold: 8.0)
coord.register("worker-1")
_ = try coord.update("worker-1", pressure: 0.4)
```

Redis-backed (interoperable across all eight reference SDKs):

```swift
let coord = try RedisCoordinator(
    redis: myRedisAdapter,         // your RediStack / Vapor Redis adapter
    coordinatorId: "prod-fleet",
    escalationThreshold: 5.0,
    releaseThreshold: 8.0)
```

The Lua script for atomic updates is exported as
`RedisCoordinator.UPDATE_AND_FETCH_SCRIPT` and is verbatim from
`spec/coordinator/README.md §1.2`. **All eight reference SDKs ship the
exact same script bytes** — Python, Node, Go, Rust, Java, C#, PHP, Swift —
guaranteeing fleet coordination across mixed-language environments.

## OIDC identity

```swift
import IAIsoIdentity

let cfg = ProviderConfig.okta(domain: "acme.okta.com", audience: "api")
// or: ProviderConfig.auth0(domain: "acme.auth0.com", audience: "api")
// or: ProviderConfig.azureAd(tenant: "tenant-id", audience: "api", v2: true)

let verifier = OidcVerifier(config: cfg)

// Fetch JWKS bytes via URLSession and inject:
verifier.setJwksFromBytes(jwksBytes)

let claims = try verifier.verify(idToken)
let scopes = OidcVerifier.deriveScopes(claims, mapping: .defaults)
```

The library is HTTP-free — `setJwksFromBytes(_:)` takes pre-fetched
bytes, so you wire in URLSession (or Alamofire, or anything else)
yourself. RSA verification is implemented via hand-rolled ASN.1 DER
encoding to build a SubjectPublicKeyInfo PEM from the JWK's
base64url-encoded `n` and `e`, then validated through
`SecKeyVerifySignature` on Apple platforms.

## Admin CLI

```bash
swift run iaiso --help
swift run iaiso conformance ./spec
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

## Conformance

```bash
swift test                                       # unit tests + 67 spec vectors
swift run iaiso conformance ./spec               # via the CLI
```

The conformance test resolves `spec/` via (in order):

1. The `IAISO_SPEC_DIR` environment variable
2. `<package-root>/spec/` (relative to the test file)
3. `./spec` in the current working directory

If your test runner is somewhere unusual, set `IAISO_SPEC_DIR` before
`swift test`.

### Float tolerance

Pressure math is specified to real-number semantics with a `1e-9`
absolute tolerance for floating-point implementations
(see `spec/README.md`). This port meets the tolerance with
straightforward IEEE-754 evaluation in `Double`.

### Cross-language parity

Audit events emitted by this port serialize byte-identically to the
Python, Node, Go, Rust, Java, C#, and PHP references for the same
input. JWTs issued by this port verify against every other reference
SDK's verifier given the same key and algorithm. Redis coordinator
state is interoperable across all eight runtimes using the same
`(keyPrefix, coordinatorId)` tuple.

## Notable engineering decisions

1. **CryptoKit + Security.framework, no JWT dependency.** HMAC via
   CryptoKit's `HMAC<SHA256>`; RSA via `SecKey` and
   `SecKeyVerifySignature`. On Linux, swift-crypto provides the same
   `Crypto` module API. **Zero third-party JWT library required.**

2. **`enum` namespaces for middleware providers.** Each provider
   (Anthropic, OpenAI, Gemini, Bedrock, Mistral, Cohere, LiteLLM) is a
   Swift `enum` containing nested `Client`, `Response`, `BoundedClient`,
   etc. types. This is the idiomatic Swift way to namespace without
   creating per-provider modules — `Anthropic.BoundedClient` reads
   cleanly and discoverability is great in Xcode's autocomplete.

3. **Hand-built canonical JSON for `Event`.** `JSONSerialization` doesn't
   guarantee key order across platforms, so `Event.toJSON()` writes
   fields in spec order (`schema_version, execution_id, kind,
   timestamp, data`) and sorts `data` keys alphabetically. Integer-valued
   floats emit as integers (`0` not `0.0`) to match the wire format of
   the seven prior ports byte-for-byte.

4. **`AnyJSON` sum type.** Swift doesn't have a great native way to
   express "any JSON-encodable value", so a small enum (`null`, `bool`,
   `int`, `double`, `string`, `array`, `object`) carries event-data
   values with full type safety. `ExpressibleBy*Literal` conformances
   make construction ergonomic — `["pressure": .double(0.42)]` works.

5. **Strict numeric validation** in `PolicyLoader`. Detects the
   "string masquerading as number" case (`"0.015"`) using runtime
   type checks against `String` and `Bool` (with extra `objCType`
   inspection on Apple platforms to filter out `Bool` bridged through
   `NSNumber`). The `wrong_type_for_number_field` policy vector is the
   one that bit Java; preempted in Swift.

6. **`@unchecked Sendable` for stateful classes** synchronized via
   `NSLock`. The compiler can't prove `MemorySink`, `JSONLFileSink`,
   `PressureEngine`, `BoundedExecution`, `RevocationList`, etc. are
   thread-safe automatically, but they are. Swift 5.9+ `@unchecked`
   is the right escape hatch for manually-locked types.

7. **`deinit` on `BoundedExecution`** runs a defensive `closeWith(false)`
   so users who forget to `close()` still get an `execution.closed`
   event. Swift's deterministic ARC fires `deinit` reliably for normal
   object lifetimes.

8. **`UPDATE_AND_FETCH_SCRIPT` as `public static let`** in
   `RedisCoordinator`. Verbatim from `spec/coordinator/README.md §1.2`.
   **All eight reference SDKs ship the exact same Lua script bytes.**

9. **JSON-only policies.** YAML support would add a third-party YAML
   parser dependency, breaking the dependency-light goal. Convert YAML
   to JSON externally if needed.

10. **HTTP-free OIDC.** `OidcVerifier.setJwksFromBytes(_:)` takes
    pre-fetched bytes. Users wire in URLSession (or any HTTP client)
    themselves. This keeps the SDK free of HTTP-stack assumptions and
    works in any environment.

## Open items

- **Conformance run** must be done on the user's machine (toolchain
  unavailability in the build sandbox — see ⚠️ above).
- **SIEM-vendor sinks** (Splunk / Datadog / Loki / Elasticsearch ECS /
  Sumo / New Relic) are not yet shipped. The `Sink` protocol is just
  `func emit(_ event: Event)` — implementing one for your stack is a
  ten-line job. Planned for `0.2.0`.
- **RSA on Linux** uses Apple's `Security.framework` on Apple platforms
  but throws on Linux. swift-crypto's `_RSA.Signing` will close that
  gap in `0.2.0`. HS256 works on every platform today.

## License

Apache-2.0. See [LICENSE](LICENSE).

## Links

- Main repository: https://github.com/SmartTasksOrg/IAISO
- Framework specification: `../../vision/README.md`
- Python reference SDK: `../iaiso-python/README.md`
- Node.js / TypeScript reference SDK: `../iaiso-node/README.md`
- Go reference SDK: `../iaiso-go/README.md`
- Rust reference SDK: `../iaiso-rust/README.md`
- Java reference SDK: `../iaiso-java/README.md`
- C# / .NET reference SDK: `../iaiso-csharp/README.md`
- PHP reference SDK: `../iaiso-php/README.md`
- Conformance porting guide: `../docs/CONFORMANCE.md`
- Normative specification: `../spec/`
