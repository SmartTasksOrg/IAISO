# IAIso Reference SDKs

This directory contains the **reference implementations** of the IAIso
framework's runtime layer, one per language. Every SDK conforms to the
same normative specification at [`spec/`](spec/) and passes the same 67
conformance vectors.

## Pick your language

| Language | Directory | Package | Status |
|---|---|---|---|
| **Python** | [`iaiso-python/`](iaiso-python/) | `iaiso` (PyPI) | Stable · `0.2.0` · 67/67 conformance · 240 tests |
| **Node.js / TypeScript** | [`iaiso-node/`](iaiso-node/) | `@iaiso/core` (npm) | Stable · `0.3.0` · 67/67 conformance · 171 tests |
| **Go** | [`iaiso-go/`](iaiso-go/) | `github.com/iaiso/iaiso-go` | Stable · `v0.1.0` · 67/67 conformance · 48 tests |
| **Rust** | [`iaiso-rust/`](iaiso-rust/) | Cargo workspace (`iaiso-core`, `iaiso-consent`, …) | Stable · `0.1.0` · 67/67 conformance · 47 tests |

Each SDK directory is **self-contained**: source code, tests,
documentation, packaging configuration. Pick the one for your stack and
follow that directory's README to install and use.

## What every SDK provides

The full framework runtime, idiomatic to its language:

- **Pressure engine** — bounded execution with configurable thresholds,
  escalation, and atomic release.
- **Consent tokens** — scope-based authorization via signed JWTs
  (HS256 / RS256), with revocation and execution binding.
- **Audit envelope** — structured events with a stable JSON Schema and
  multiple sink implementations (stdout, JSONL, webhook, fanout, plus
  SIEM sinks for Splunk, Datadog, Loki, Elastic, Sumo Logic, New Relic).
- **Policy-as-code** — JSON / YAML configuration with schema validation.
- **Coordinator** — cross-execution pressure aggregation with in-memory
  and Redis-backed implementations.
- **LLM middleware** — bounded clients for major providers (Anthropic,
  OpenAI, LangChain, Gemini, Bedrock, Mistral, Cohere, LiteLLM proxy).
- **OIDC identity** — verify tokens from Okta, Auth0, Azure AD, or any
  conforming OIDC provider; map claims to IAIso scopes.
- **Metrics & tracing** — Prometheus and OpenTelemetry integrations.
- **Admin CLI** — operator commands for policy validation, token
  management, audit inspection, and conformance.

## Cross-language interoperability

Because every SDK targets the same spec, instances in different
languages cooperate without bridges:

- **Audit events** emitted by any SDK validate against the same JSON
  Schemas in `spec/events/` and can be consumed by any other SDK.
- **Consent tokens** issued by one SDK verify in another, given the
  same signing key and algorithm.
- **Coordinator state** is shared via the normative Redis keyspace and
  Lua script in `spec/coordinator/README.md`. A Python worker and a
  Node worker pointed at the same Redis instance with matching
  `coordinator_id` see each other's pressure live.

This means you can run a Python orchestrator alongside Node-based agent
fleet without reinventing wire formats anywhere.

## Shared resources

All SDK directories reference these:

- **[`spec/`](spec/)** — the normative specification: pressure math,
  consent tokens, audit events, policy format, coordinator wire
  contract, plus 67 machine-verifiable test vectors and JSON Schemas.
- **[`docs/`](docs/)** — language-agnostic framework documentation:
  conformance porting guide, threat model, calibration methodology,
  coordination model, integration patterns, and operational playbooks.

When extending the framework, the spec is the source of truth. New
features are designed in `spec/`, implemented in each SDK, and verified
by adding conformance vectors that all SDKs must pass.

## Adding a new language port

The porting workflow lives in [`docs/CONFORMANCE.md`](docs/CONFORMANCE.md).
The shortest path:

1. Pick a directory name: `iaiso-go/`, `iaiso-rust/`, `iaiso-java/`, etc.
2. Implement the spec in your language (use Python and Node as worked
   examples — both pass the same vectors).
3. Run the 67 conformance vectors against your implementation; iterate
   until they all pass.
4. Add your SDK to the **Pick your language** table above and to
   `docs/CONFORMANCE.md`'s shipping ports table.

Conformance is the gate; the rest is style.

## License

Apache-2.0. Each SDK directory carries its own `LICENSE` file
appropriate to its packaging conventions. The framework specification
in `spec/` is permissively licensed for all conforming implementations.
