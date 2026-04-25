# iaiso-ruby

**Ruby reference SDK for the IAIso bounded-agent-execution framework.**

IAIso adds pressure-based rate limiting, scope-based authorization, and
structured audit logging to LLM agent loops. This is the Ruby
implementation, conformant to **IAIso spec 1.0**.

> Built on **Ruby 3.0+**. Single gem (`iaiso`) with capabilities
> cleanly separated into modules under `IAIso::*`. Passes all
> **67 spec conformance vectors** plus **54 unit tests** (109
> assertions). Wire-format compatible with the
> [Python](../iaiso-python/), [Node](../iaiso-node/),
> [Go](../iaiso-go/), [Rust](../iaiso-rust/), [Java](../iaiso-java/),
> [C#](../iaiso-csharp/), [PHP](../iaiso-php/), and
> [Swift](../iaiso-swift/) reference SDKs — same audit events, same
> JWTs, same Redis Lua script.

## Workspace layout

```
iaiso-ruby/
├── iaiso.gemspec                # gem metadata, zero runtime deps
├── Rakefile                     # rake test
├── README.md, LICENSE, .gitignore, CHANGELOG.md
├── exe/iaiso                    # admin CLI launcher
├── spec/                        # normative spec + 67 conformance vectors
├── lib/
│   └── iaiso/
│       ├── version.rb           # IAIso::VERSION = "0.1.0"
│       ├── audit/               # event envelope + base sinks
│       ├── core/                # pressure engine + BoundedExecution
│       ├── consent/             # JWT issuer/verifier (HS256/RS256)
│       ├── policy/              # JSON policy loader
│       ├── coordination/        # in-memory + Redis coordinator
│       ├── middleware/          # 7 LLM provider wrappers
│       ├── identity/            # OIDC verifier + scope mapping
│       ├── metrics/             # Prometheus sink (duck-typed)
│       ├── observability/       # OpenTelemetry sink (duck-typed)
│       ├── conformance/         # vector runner
│       └── cli.rb               # admin CLI subcommand dispatch
└── test/                        # Minitest tests (54 tests, 109 assertions)
```

## Install

```bash
gem install iaiso
```

Or in your `Gemfile`:

```ruby
gem "iaiso", "~> 0.1.0"
```

Requires **Ruby 3.0** or later. The SDK uses only built-in standard
library: `json`, `openssl`, `base64`, `securerandom`, `set`, `monitor`.
**Zero third-party runtime dependencies.** Minitest is in stdlib;
Rake is dev-only.

## Quick start

```ruby
require "iaiso/audit"
require "iaiso/core"

sink = IAIso::Audit::MemorySink.new

IAIso::Core::BoundedExecution.run(audit_sink: sink) do |exec|
  outcome = exec.record_tool_call("search", tokens: 500)
  if outcome == IAIso::Core::StepOutcome::ESCALATED
    # Layer 4: request human review per the escalation template
  end
end
```

The `run` block automatically emits `execution.closed` on exit, even
when the block raises.

## LLM middleware

Seven provider adapters under `IAIso::Middleware::*`. Each defines a
duck-typed contract that you satisfy with a thin adapter around the
upstream gem:

```ruby
require "iaiso/middleware"

class MyAnthropicAdapter
  # Wrap anthropic-ruby, Faraday, or any HTTP client.
  def messages_create(params)
    # ... call upstream, return IAIso::Middleware::Anthropic::Response
  end
end

bounded = IAIso::Middleware::Anthropic::BoundedClient.new(
  raw: MyAnthropicAdapter.new,
  execution: exec,
)
resp = bounded.messages_create(params)
```

The duck-typed pattern keeps the SDK free of any specific provider
gem. Adapters: `Anthropic`, `OpenAI` (works with any
OpenAI-compatible endpoint including Azure OpenAI, vLLM, TGI, LiteLLM
proxy, Together, Groq), `Gemini`, `Bedrock` (Converse + InvokeModel),
`Mistral`, `Cohere`, and `LiteLLM` (proxy-pattern helper).

## Distributed coordination

In-memory:

```ruby
require "iaiso/coordination"

coord = IAIso::Coordination::SharedPressureCoordinator.new(
  escalation_threshold: 5.0,
  release_threshold: 8.0,
  on_escalation: ->(snap) { puts "escalated at #{snap.aggregate_pressure}" },
)
coord.register("worker-1")
coord.update("worker-1", 0.4)
```

Redis-backed (interoperable with all eight other reference SDKs):

```ruby
# Wrap redis-rb, hiredis-client, or any Redis client.
class MyRedisAdapter
  def initialize(redis); @redis = redis; end
  def eval(script, keys:, args:); @redis.eval(script, keys: keys, argv: args); end
  def hset(key, pairs); pairs.each { |k, v| @redis.hset(key, k, v) }; end
  def hkeys(key); @redis.hkeys(key); end
end

coord = IAIso::Coordination::RedisCoordinator.new(
  redis: MyRedisAdapter.new(Redis.new),
  coordinator_id: "prod-fleet",
  escalation_threshold: 5.0,
  release_threshold: 8.0,
)
```

The Lua script used for atomic updates is exported as
`RedisCoordinator::UPDATE_AND_FETCH_SCRIPT` and is verbatim from
`spec/coordinator/README.md §1.2`. **All nine reference SDKs ship
the exact same script bytes** — Python, Node, Go, Rust, Java, C#, PHP,
Swift, Ruby — guaranteeing fleet coordination across mixed-language
environments.

## OIDC identity

```ruby
require "iaiso/identity"

cfg = IAIso::Identity::ProviderConfig.okta(
  domain: "acme.okta.com",
  audience: "api://my-resource",
)
# or: ProviderConfig.auth0(domain: "...", audience: "...")
# or: ProviderConfig.azure_ad(tenant: "...", audience: "...", v2: true)

verifier = IAIso::Identity::OidcVerifier.new(config: cfg)

# Fetch JWKS bytes via Net::HTTP / Faraday / HTTParty — anything —
# then inject:
verifier.set_jwks_from_bytes(jwks_bytes)

claims = verifier.verify(id_token)
scopes = IAIso::Identity::OidcVerifier.derive_scopes(claims, IAIso::Identity::ScopeMapping.defaults)
```

The library is HTTP-free — `set_jwks_from_bytes` takes pre-fetched
bytes, so users wire in their preferred HTTP client. RSA verification
uses `OpenSSL::ASN1` natively to construct the SubjectPublicKeyInfo
from the JWK's base64url-encoded `n` and `e` fields — no hand-rolled
DER like the PHP / Swift ports needed.

## Audit sinks

The base sinks (`MemorySink`, `NullSink`, `StdoutSink`, `FanoutSink`,
`JSONLFileSink`) live in `IAIso::Audit` and are always available.

> **Note on SIEM sinks**: SIEM-vendor sinks (Splunk HEC, Datadog Logs,
> Loki, Elasticsearch ECS, Sumo Logic, New Relic Logs) are documented
> and tested in the Python, Node, and Go references. The Ruby port
> ships with the base sinks only in 0.1.0; SIEM sinks are deferred to
> 0.2.0. For now, use `JSONLFileSink` plus a forwarder (Vector,
> Fluent Bit, or any log shipper), or implement a sink in two methods:
> any object responding to `emit(event)` is a valid sink (Ruby duck
> typing).

## Metrics and tracing

`IAIso::Metrics::PrometheusSink` wraps duck-typed counter / gauge /
histogram objects. The official `prometheus-client` gem satisfies
these contracts with thin adapters.

`IAIso::Observability::OtelSpanSink` wraps a duck-typed tracer /
span. The official `opentelemetry-api` gem satisfies these contracts.

## Admin CLI

```bash
./exe/iaiso --help
./exe/iaiso conformance ./spec
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

When the gem is installed, the CLI is available as `iaiso` automatically
via `bundle exec iaiso` or directly if your gem bin path is on `$PATH`.

## Conformance

```bash
rake test                            # 54 unit tests + the 67-vector conformance suite
./exe/iaiso conformance ./spec       # via the CLI
```

Or programmatically:

```ruby
require "iaiso/conformance"
results = IAIso::Conformance::Runner.run_all("./spec")
puts "#{results.passed}/#{results.total}"
```

### Float tolerance

Pressure math is specified to real-number semantics with a `1e-9`
absolute tolerance for floating-point implementations
(see `spec/README.md`). This port meets the tolerance with
straightforward IEEE-754 evaluation in `Float`.

### Cross-language parity

Audit events emitted by this port serialize byte-identically to the
Python, Node, Go, Rust, Java, C#, PHP, and Swift references for the
same input. JWTs issued by this port verify against every other
reference SDK's verifier given the same key and algorithm — confirmed
in this port's bring-up by reading a token from
`spec/consent/vectors.json` (signed by another reference SDK) and
verifying it cleanly. Redis coordinator state is interoperable across
all nine runtimes using the same `(key_prefix, coordinator_id)`
tuple.

## Development

```bash
bundle install         # only installs rake
rake test              # all 54 unit tests + 67 conformance vectors
ruby test/conformance_test.rb   # just the spec suite
./exe/iaiso conformance ./spec  # via the CLI
```

## Versioning

- Gem versions track SDK features (`0.1.0`, `0.2.0`, ...).
- **Spec version** is `1.0`, defined in `./spec/VERSION`. A MINOR spec
  bump never breaks existing vectors; a MAJOR spec bump ships a
  migration guide.
- Breaking changes in the public API are signaled by a MAJOR gem
  version bump.

## Notable engineering decisions

1. **Zero runtime dependencies.** Ruby's stdlib has `json`, `openssl`,
   `base64`, `securerandom`, `set`, `monitor` — that's all we need.
   JWT signing/verification is hand-rolled in ~100 lines using
   `OpenSSL::HMAC.digest` for HS256, `OpenSSL::PKey::RSA#sign` /
   `#verify` for RS256, with `OpenSSL.fixed_length_secure_compare`
   for constant-time signature comparison. Minitest is in stdlib.
   Rake is dev-only.

2. **Hash insertion order preserved natively.** Ruby has guaranteed
   hash insertion order since 1.9. This means `JSON.generate({iss:
   ..., sub: ..., iat: ...})` emits keys in the exact spec-mandated
   claim order — **no `canonicalJSONDataOrdered` like Swift, no
   ordered-tuple list like Java, no manual key tracking**. Cross-
   language JWT byte compatibility was free.

3. **`OpenSSL::ASN1` for SubjectPublicKeyInfo.** Building an RSA
   public key from JWK `n` / `e` fields is one ASN.1 sequence away.
   No hand-rolled DER like the PHP / Swift ports needed.

4. **`MonitorMixin` for thread-safe classes** — re-entrant by default,
   so the engine doesn't deadlock when emit-callbacks land on the
   same thread.

5. **`Data.define`** (Ruby 3.2+ — gracefully degrades to `Struct` on
   3.0–3.1 if needed) for true immutable value structs (`StepInput`,
   `PressureSnapshot`, `Snapshot`, `VectorResult`).

6. **Block-based `BoundedExecution.run`** — Ruby's signature pattern.
   `BoundedExecution.run(audit_sink: sink) { |exec| ... }` reads
   exactly like `File.open` with automatic cleanup including the
   `execution.closed` event on exception.

7. **`autoload` for lazy module loading** — consumers who only need
   `IAIso::Core` don't pay for `IAIso::Identity` or
   `IAIso::Middleware::Cohere`.

8. **No NSNumber/Bool ambiguity.** Ruby distinguishes `Integer`,
   `Float`, `TrueClass`, `FalseClass` cleanly. Skipped the bug class
   that bit Java, Swift, and PHP — strict numeric typing in
   `Loader.numeric_value` is a clean three-line check.

9. **Frozen string literals** (`# frozen_string_literal: true`) at
   the top of every file — Ruby idiom for performance and immutability.

10. **JSON-only policies.** Ruby's stdlib has no YAML parser; pulling
    in `psych` would compromise the dependency-light pitch. Convert
    YAML to JSON externally if needed.

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
- C# / .NET reference SDK: `../iaiso-csharp/README.md`
- PHP reference SDK: `../iaiso-php/README.md`
- Swift reference SDK: `../iaiso-swift/README.md`
- Conformance porting guide: `../docs/CONFORMANCE.md`
- Normative specification: `../spec/`
