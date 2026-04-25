# iaiso-php

**PHP reference SDK for the IAIso bounded-agent-execution framework.**

IAIso adds pressure-based rate limiting, scope-based authorization, and
structured audit logging to LLM agent loops. This is the PHP
implementation, conformant to **IAIso spec 1.0**.

> Built on **PHP 8.2+**. Single Composer package (`iaiso/iaiso`) with
> capabilities cleanly separated into sub-namespaces under `IAIso\`,
> so consumers `use` only what they need. Passes all
> **67 spec conformance vectors** plus **53 unit tests**. Wire-format
> compatible with the [Python](../iaiso-python/), [Node](../iaiso-node/),
> [Go](../iaiso-go/), [Rust](../iaiso-rust/), [Java](../iaiso-java/),
> and [C#/.NET](../iaiso-csharp/) reference SDKs — same audit events,
> same JWTs, same Redis Lua script.

## Workspace layout

PSR-4 autoloading under `IAIso\`. One class per file, ten capability
sub-namespaces:

```
iaiso-php/
├── composer.json                  # iaiso/iaiso, php >=8.2, dev-only PHPUnit
├── phpunit.xml                    # unit + conformance test suites
├── README.md, LICENSE, .gitignore
├── bin/iaiso                      # admin CLI launcher (#!/usr/bin/env php)
├── spec/                          # normative spec + conformance vectors
├── src/
│   ├── Audit/                     # event envelope + base sinks
│   ├── Core/                      # pressure engine + BoundedExecution
│   ├── Consent/                   # JWT issuer/verifier (HS256/RS256)
│   ├── Policy/                    # JSON policy loader
│   ├── Coordination/              # in-memory + Redis coordinator
│   ├── Middleware/                # 7 LLM provider wrappers (sub-namespaces)
│   ├── Identity/                  # OIDC verifier + scope mapping
│   ├── Metrics/                   # Prometheus sink (structural)
│   ├── Observability/             # OpenTelemetry sink (structural)
│   ├── Conformance/               # vector runner
│   └── Cli/                       # admin CLI Application class
└── tests/
    ├── Unit/                      # PHPUnit tests (Audit, Core, Consent,
    │                              # Policy, Coordination, Identity, Middleware)
    └── Conformance/               # spec-vector suite
```

## Install

```bash
composer require iaiso/iaiso
```

Or in `composer.json`:

```json
{
    "require": {
        "iaiso/iaiso": "^0.1.0"
    }
}
```

Requires **PHP 8.2** or later. The SDK uses only built-in extensions:
`ext-json`, `ext-openssl`, `ext-hash`, `ext-mbstring` — all of which
ship with mainstream PHP distributions. **Zero third-party runtime
dependencies.** PHPUnit is dev-only.

## Quick start

```php
<?php
require 'vendor/autoload.php';

use IAIso\Audit\MemorySink;
use IAIso\Core\BoundedExecution;
use IAIso\Core\BoundedExecutionOptions;
use IAIso\Core\StepOutcome;

$sink = new MemorySink();
BoundedExecution::run(
    new BoundedExecutionOptions(auditSink: $sink),
    function ($exec): void {
        $outcome = $exec->recordToolCall('search', 500);
        if ($outcome === StepOutcome::Escalated) {
            // Layer 4: request human review per the escalation template
        }
    },
);
```

## LLM middleware

Seven provider adapters under `IAIso\Middleware\*`. Each provider
defines a structural `Client` interface you satisfy with a thin adapter
around the upstream SDK:

```php
use IAIso\Middleware\Anthropic\BoundedClient;
use IAIso\Middleware\Anthropic\Client;
use IAIso\Middleware\Anthropic\ContentBlock;
use IAIso\Middleware\Anthropic\Options;
use IAIso\Middleware\Anthropic\Response;

class MyAnthropicAdapter implements Client
{
    // Wraps anthropic-php-sdk, Saloon, Guzzle, or any HTTP client.
    public function messagesCreate(array $params): Response
    {
        // ... call the upstream SDK, map into Anthropic\Response
    }
}

$bounded = new BoundedClient(new MyAnthropicAdapter(), $exec, Options::defaults());
$resp = $bounded->messagesCreate($params);
```

The structural pattern keeps the SDK free of any specific provider
package. Adapters: `Anthropic`, `OpenAi` (works with any
OpenAI-compatible endpoint including Azure OpenAI, vLLM, TGI, LiteLLM
proxy, Together, Groq), `Gemini`, `Bedrock` (Converse + InvokeModel),
`Mistral`, `Cohere`, and `LiteLlm` (proxy-pattern helper).

## Distributed coordination

In-memory:

```php
use IAIso\Coordination\SharedPressureCoordinator;

$coord = SharedPressureCoordinator::builder()
    ->escalationThreshold(5.0)
    ->releaseThreshold(8.0)
    ->build();
$coord->register('worker-1');
$coord->update('worker-1', 0.4);
```

Redis-backed (interoperable with Python, Node, Go, Rust, Java, and C# references):

```php
use IAIso\Coordination\RedisClient;
use IAIso\Coordination\RedisCoordinator;

// RedisClient is a structural interface — supply an adapter around
// phpredis, predis/predis, or any Redis client library.
$coord = RedisCoordinator::builder()
    ->redis($myRedisAdapter)
    ->coordinatorId('prod-fleet')
    ->escalationThreshold(5.0)
    ->releaseThreshold(8.0)
    ->build();
```

The Lua script used for atomic updates is exported as
`RedisCoordinator::UPDATE_AND_FETCH_SCRIPT` and is verbatim from
`spec/coordinator/README.md §1.2`. **All seven reference SDKs ship the
exact same script bytes** — Python, Node, Go, Rust, Java, C#, PHP —
guaranteeing fleet coordination across mixed-language environments.

## Audit sinks

The base sinks (`MemorySink`, `NullSink`, `StdoutSink`, `FanoutSink`,
`JsonlFileSink`) live in `IAIso\Audit` and are always available.

> **Note on SIEM sinks**: SIEM-vendor sinks (Splunk HEC, Datadog Logs,
> Loki, Elasticsearch ECS, Sumo Logic, New Relic Logs) are documented
> and tested in the Python, Node, and Go references. The PHP port
> ships with the base sinks only in 0.1.0; SIEM sinks are deferred to
> 0.2.0. For now, use `JsonlFileSink` plus a forwarder (Vector,
> Fluent Bit, or any log shipper), or implement a sink for your vendor
> in two lines — the `Sink` interface is just `public function emit(Event $event): void`.

## OIDC identity

```php
use IAIso\Identity\OidcVerifier;
use IAIso\Identity\ProviderConfig;
use IAIso\Identity\ScopeMapping;

$cfg = ProviderConfig::okta('acme.okta.com', 'api://my-resource');
// or: ProviderConfig::auth0('acme.auth0.com', 'api')
// or: ProviderConfig::azureAd('tenant-id', 'api://my-resource', v2: true)

$verifier = new OidcVerifier($cfg);

// Fetch JWKS bytes via curl, Guzzle, Symfony HttpClient — anything —
// then inject:
$verifier->setJwksFromBytes($jwksBytes);

$claims = $verifier->verify($idToken);
$scopes = OidcVerifier::deriveScopes($claims, ScopeMapping::defaults());
```

The library is HTTP-free — `setJwksFromBytes()` takes pre-fetched
bytes, so users wire in their preferred HTTP client. RSA verification
is implemented in-house: the library hand-builds an RSA
`SubjectPublicKeyInfo` PEM from the JWK's base64url-encoded `n` and
`e` fields using minimal ASN.1 DER encoding, then hands it to
`openssl_verify()`.

## Metrics and tracing

`IAIso\Metrics` exposes `PrometheusSink` with structural
`Counter`/`CounterVec`/`Gauge`/`GaugeVec`/`Histogram` interfaces. Adapt
the official `promphp/prometheus_client_php` package.

`IAIso\Observability` exposes `OtelSpanSink` with structural `Tracer`
and `Span` interfaces. Adapt the `open-telemetry/opentelemetry`
packages.

## Admin CLI

```bash
./bin/iaiso --help
./bin/iaiso conformance ./spec
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

When the package is installed via `composer require iaiso/iaiso`, the
CLI is available as `vendor/bin/iaiso` automatically.

## Conformance

```bash
composer test                                                 # build + 53 unit tests + 67 spec vectors
./bin/iaiso conformance ./spec                                # via the CLI
```

Or programmatically:

```php
use IAIso\Conformance\ConformanceRunner;

$results = ConformanceRunner::runAll('./spec');
echo $results->countPassed() . '/' . $results->countTotal();
```

### Float tolerance

Pressure math is specified to real-number semantics with a `1e-9`
absolute tolerance for floating-point implementations
(see `spec/README.md`). This port meets the tolerance with
straightforward IEEE-754 evaluation in `float`.

### Cross-language parity

Audit events emitted by this port serialize byte-identically to the
Python, Node, Go, Rust, Java, and C# references for the same input.
JWTs issued by this port verify against every other reference SDK's
verifier given the same key and algorithm. Redis coordinator state is
interoperable across all seven runtimes using the same
`(keyPrefix, coordinatorId)` tuple.

## Development

```bash
composer install
composer test           # PHPUnit
phpunit --testsuite unit         # only unit tests
phpunit --testsuite conformance  # only the spec suite
./bin/iaiso conformance ./spec   # via the CLI
```

## Versioning

- Package versions track SDK features (`0.1.0`, `0.2.0`, …).
- **Spec version** is `1.0`, defined in `./spec/VERSION`. A MINOR spec
  bump never breaks existing vectors; a MAJOR spec bump ships a
  migration guide.
- Breaking changes in the public API are signaled by a MAJOR package
  version bump.

## Notable engineering decisions

1. **Zero runtime dependencies.** PHP 8.2+ ships `ext-json`,
   `ext-openssl`, `ext-hash`, `ext-mbstring` — that's all we need.
   JWT signing/verification hand-rolled in ~150 lines using
   `hash_hmac` for HS256, `openssl_sign`/`openssl_verify` for RS256,
   with `hash_equals` for constant-time signature comparison.

2. **Native PHP 8 enums** for `Lifecycle`, `StepOutcome`, `Algorithm`,
   `CoordinatorLifecycle` — backed by string with the lowercase wire
   value, so `Lifecycle::Running->value === "running"` for free.

3. **PSR-4 strict — one class per file.** 126 classes load cleanly
   under the `IAIso\` prefix via Composer's optimized autoloader.

4. **Readonly properties + constructor promotion** throughout — idiomatic
   PHP 8.1+, immutable by default. Builders for the aggregate types.

5. **`Event::toJson()` is hand-built**, not `json_encode($this)`.
   Field order is the spec order (`schema_version, execution_id, kind,
   timestamp, data`); `data` keys are `ksort`'d alphabetically;
   integer-valued floats emit as `0` not `0.0` to match the wire
   format of all six other ports.

6. **`__destruct` on `BoundedExecution`** as a defensive `closeWith(false)`
   so even users who forget to `close()` still get the
   `execution.closed` event. PHP's GC fires `__destruct` reliably for
   normal object lifetimes.

7. **JSON-only policies.** PHP has no built-in YAML parser; pulling in
   `symfony/yaml` would violate the zero-dependency choice. Convert YAML
   to JSON externally if needed.

8. **Hand-rolled ASN.1 DER encoding for JWKS public keys.** The PHP
   `openssl_*` family doesn't provide a one-liner for "RSA public key
   from raw n+e", so `OidcVerifier` builds a minimal
   `SubjectPublicKeyInfo` (BIT STRING wrapping a SEQUENCE of two
   INTEGERs) and base64-encodes it as PEM. Tested end-to-end with a
   freshly generated 2048-bit RSA key.

9. **`array_is_list()` for list-vs-map disambiguation.** PHP arrays
   double as both, so the policy validator and Event JSON encoder use
   this PHP 8.1+ helper to reject documents like `[1,2,3]` as policies
   (must be a mapping) or to render arrays correctly in audit JSON.

10. **`RedisShadowCoordinator` subclass trick** to expose protected
    methods (`setPressuresFromMap`, `evaluate`) to `RedisCoordinator`
    without making them public on `SharedPressureCoordinator`. PHP
    doesn't have package-private visibility, so this is a clean
    alternative to making the API surface noisier.

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
- Conformance porting guide: `../docs/CONFORMANCE.md`
- Normative specification: `../spec/`
