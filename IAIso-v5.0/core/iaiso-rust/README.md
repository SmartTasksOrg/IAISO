# iaiso-rust

**Rust reference SDK for the IAIso bounded-agent-execution framework.**

IAIso adds pressure-based rate limiting, scope-based authorization, and
structured audit logging to LLM agent loops. This workspace is the Rust
implementation, conformant to **IAIso spec 1.0**.

> Targets the normative specification shipped in [`./spec/`](./spec/).
> Passes all 67 spec conformance vectors plus 47 unit tests + 1 doc
> test. Built alongside the [Python](../iaiso-python/),
> [Node](../iaiso-node/), and [Go](../iaiso-go/) reference SDKs; all
> four implementations produce identical event streams and consent
> tokens for identical inputs.

## Workspace layout

This is a Cargo workspace. Each capability is its own crate so users
add only what they need:

```
iaiso-rust/
├── Cargo.toml                          # workspace root
├── README.md, LICENSE, .gitignore
├── spec/                               # normative spec + conformance vectors
├── crates/
│   ├── core/                           # pressure engine + BoundedExecution
│   ├── consent/                        # JWT issuer/verifier (HS256/RS256)
│   ├── audit/                          # event envelope + base sinks
│   ├── policy/                         # JSON + YAML policy loader
│   ├── coordination/                   # in-memory + Redis coordinator
│   ├── middleware/                     # 7 LLM provider adapters
│   ├── identity/                       # OIDC verifier + scope mapping
│   ├── metrics/                        # Prometheus sink (structural)
│   ├── observability/                  # OTel tracing sink (structural)
│   ├── conformance/                    # vector runner
│   └── cli/                            # admin CLI implementation
└── cmd/
    ├── iaiso/                          # `iaiso` admin CLI binary
    └── iaiso-conformance/              # `iaiso-conformance` binary
```

## Install

Add the crates you need to your `Cargo.toml`:

```toml
[dependencies]
iaiso-core = "0.1"
iaiso-consent = "0.1"
iaiso-audit = "0.1"
# ... etc
```

Requires Rust **≥ 1.75** (workspace MSRV).

The SDK takes a small set of direct dependencies: `serde`, `serde_json`,
`serde_yaml`, `thiserror`, `parking_lot`, `chrono`, `jsonwebtoken`,
`base64`. LLM provider clients, Redis, Prometheus, and OpenTelemetry
are integrated via **structural traits**, so you can use the SDK with
any compatible client without IAIso taking a Cargo dependency on those
libraries.

## Quick start

```rust
use iaiso_audit::{MemorySink, Sink};
use iaiso_core::{BoundedExecution, BoundedExecutionOptions, StepOutcome};
use std::sync::Arc;

fn main() {
    let sink: Arc<dyn Sink> = Arc::new(MemorySink::new());
    BoundedExecution::run(
        BoundedExecutionOptions {
            audit_sink: sink.clone(),
            ..Default::default()
        },
        |exec| {
            let outcome = exec.record_tool_call("search", 500)?;
            if outcome == StepOutcome::Escalated {
                // Layer 4: request human review per the escalation template
            }
            Ok(())
        },
    )
    .unwrap();
}
```

## LLM middleware

The middleware crate exposes seven provider adapters under
`iaiso_middleware::*`. Each provider defines a structural `Client`
trait you satisfy with a thin adapter around the upstream SDK:

```rust
use iaiso_middleware::anthropic::{BoundedClient, Client, Options, Response};
use serde_json::Value;

struct MyAdapter { /* wraps the upstream SDK */ }

impl Client for MyAdapter {
    fn messages_create(&self, params: &Value) -> Result<Response, String> {
        // call your favorite Anthropic Rust client, map response to
        // `Response`, return.
        todo!()
    }
}

let adapter = MyAdapter { /* ... */ };
let bounded = BoundedClient::new(adapter, &exec, Options::default());
let resp = bounded.messages_create(&serde_json::json!({...}))?;
```

The structural pattern keeps the SDK free of any specific provider
crate. Adapters: `anthropic`, `openai` (works with any
OpenAI-compatible endpoint including LiteLLM proxy, Azure, vLLM, TGI,
Together, Groq), `gemini`, `bedrock` (Converse + InvokeModel),
`mistral`, `cohere`, `litellm` (proxy-pattern helper).

## Distributed coordination

```rust
use iaiso_coordination::{
    Callbacks, CoordinatorOptions, RedisClient, RedisCoordinator,
    RedisCoordinatorOptions, SharedPressureCoordinator,
};
```

In-memory coordinator:

```rust
let c = SharedPressureCoordinator::new(CoordinatorOptions::defaults())?;
c.register("worker-1");
c.update("worker-1", 0.4)?;
```

Redis-backed (interoperable with Python, Node, and Go references):

```rust
// `RedisClient` is a structural trait — supply an adapter around
// redis-rs, redis::Client, or your own implementation.
let c = RedisCoordinator::new(RedisCoordinatorOptions {
    redis: Arc::new(my_redis_adapter),
    coordinator_id: "prod-fleet".to_string(),
    /* ... */
})?;
```

The Lua script used for atomic updates is exported as
`coordination::UPDATE_AND_FETCH_SCRIPT` and is verbatim from
`spec/coordinator/README.md §1.2`.

## Audit sinks

The base sinks (`MemorySink`, `NullSink`, `StdoutSink`, `FanoutSink`,
`JsonlFileSink`) live in `iaiso-audit` and are always available.

SIEM-vendor sinks (Splunk HEC, Datadog Logs, Loki, Elasticsearch ECS,
Sumo Logic, New Relic Logs) are gated behind Cargo features:

```toml
iaiso-audit = { version = "0.1", features = ["splunk", "datadog"] }
# or "all-sinks"
```

> Note: SIEM-sink wire formats are documented and tested in the
> Python, Node, and Go reference ports. The Rust implementations of
> these sinks are not yet shipped in this version (the architecture is
> in place; the bodies are pending). For now, use `JsonlFileSink` plus
> a forwarder, or contribute the missing implementations following the
> Python port's `iaiso/audit/sinks/` as the reference.

## OIDC identity

```rust
use iaiso_identity::{
    auth0_config, derive_scopes, issue_from_oidc, OidcVerifier,
    ScopeMapping,
};
```

Preset factories: `okta_config`, `auth0_config`, `azure_ad_config`.
The generic `ProviderConfig` works against any conforming OIDC
provider. The crate is HTTP-free — `OidcVerifier::set_jwks_from_bytes`
takes pre-fetched JWKS bytes, so users wire in `reqwest` or any other
HTTP client to fetch the discovery doc.

## Metrics and tracing

`iaiso-metrics` exposes a `PrometheusSink` with structural
`Counter` / `CounterVec` / `Gauge` / `GaugeVec` / `Histogram` traits.
Adapt the official `prometheus` or `prometheus-client` crate.

`iaiso-observability` exposes `OtelSpanSink` with structural `Tracer`
and `Span` traits. Adapt the `opentelemetry` crate.

## Admin CLI

Two binaries ship with the workspace:

```bash
cargo install --path cmd/iaiso
cargo install --path cmd/iaiso-conformance
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
iaiso-conformance ./spec
```

## Conformance

```bash
cargo run -p iaiso-conformance-bin -- ./spec

# Output:
# [PASS] pressure: 20/20
# [PASS] consent: 23/23
# [PASS] events: 7/7
# [PASS] policy: 17/17
#
# conformance: 67/67 vectors passed
```

Or programmatically:

```rust
let results = iaiso_conformance::run_all(std::path::Path::new("./spec"))?;
let (pass, total) = results.count_passed();
```

### Float tolerance

Pressure math is specified to real-number semantics with a `1e-9`
absolute tolerance for floating-point implementations
(see `spec/README.md`). This port meets the tolerance with
straightforward IEEE-754 evaluation.

### Cross-language parity

Events emitted by this port validate against the same JSON Schemas
(`spec/events/envelope.schema.json`, `spec/events/payloads.schema.json`)
as the Python, Node, and Go references. Consent tokens issued by this
port verify against the Python `ConsentVerifier`, Node
`ConsentVerifier`, and Go `Verifier` (and vice versa) given the same
key and algorithm. Redis coordinator state is interoperable across all
four runtimes using the same `(key_prefix, coordinator_id)` tuple.

## Development

```bash
cargo build --workspace
cargo test --workspace
cargo run -p iaiso-conformance-bin -- ./spec
```

### MSRV pinning

The `consent` and `identity` crates pin `simple_asn1 = "=0.6.2"`,
`time = "=0.3.36"`, and `indexmap = "=2.6.0"` to keep the workspace
buildable on Rust 1.75. Newer minor releases of those crates require
edition2024 (Rust 1.85+). When the workspace MSRV is bumped, those
pins can be removed.

## Versioning

- Crate versions track SDK features (`0.1.0`, `0.2.0`, …).
- **Spec version** is `1.0`, defined in `./spec/VERSION`. A MINOR spec
  bump never breaks existing vectors; a MAJOR spec bump ships a
  migration guide.
- Breaking changes in the public API are signaled by a MAJOR crate bump.

## License

Apache-2.0. See [LICENSE](LICENSE).

## Links

- Main repository: https://github.com/SmartTasksOrg/IAISO
- Framework specification: `../../vision/README.md` in the repo
- Python reference SDK: `../iaiso-python/README.md` in the repo
- Node reference SDK: `../iaiso-node/README.md` in the repo
- Go reference SDK: `../iaiso-go/README.md` in the repo
- Conformance porting guide: `../docs/CONFORMANCE.md` in the repo
- Normative specification: `../spec/` in the repo
