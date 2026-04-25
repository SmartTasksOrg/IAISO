# Changelog

All notable changes to the iaiso Ruby gem are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — initial release

First public release. Tracks IAIso spec 1.0.

### Added
- `IAIso::Audit` — `Event` envelope with hand-built canonical JSON
  serialization (spec field order, alphabetical `data` key sorting,
  integer-valued floats emit as integers); `Sink` contract; 5 sinks
  (Memory, Null, Stdout, Fanout, JSONLFile)
- `IAIso::Core` — `Lifecycle`, `StepOutcome` (string constants),
  `Clock` with WallClock / ScriptedClock / ClosureClock impls,
  `PressureConfig`, `PressureEngine`, `BoundedExecution` with
  block-based `run` for automatic cleanup
- `IAIso::Consent` — `Algorithm` constants, hand-rolled JWT codec
  using OpenSSL stdlib for HS256 (`HMAC.digest`) and RS256
  (`PKey::RSA#sign`/`#verify`), constant-time signature comparison
  via `OpenSSL.fixed_length_secure_compare`. `Issuer` and `Verifier`
  with full claim-order control via Ruby's hash insertion-order
  preservation.
- `IAIso::Policy` — JSON-only policy loader, validator, all 4
  aggregators (Sum, Mean, Max, WeightedSum). Strict numeric typing
  rejects strings and Bools.
- `IAIso::Coordination` — `SharedPressureCoordinator` with
  `MonitorMixin` thread safety; `RedisCoordinator` with
  `UPDATE_AND_FETCH_SCRIPT` verbatim from
  `spec/coordinator/README.md §1.2`, byte-identical to all eight
  other reference SDKs.
- `IAIso::Middleware` — 7 LLM provider adapters (Anthropic, OpenAI,
  Gemini, Bedrock, Mistral, Cohere, LiteLLM) with duck-typed `Client`
  contracts and `BoundedClient` wrappers
- `IAIso::Identity` — OIDC verifier with Okta / Auth0 / Azure AD
  presets. Uses `OpenSSL::ASN1` natively to construct
  SubjectPublicKeyInfo from JWK n/e fields — no hand-rolled DER
  required.
- `IAIso::Metrics::PrometheusSink` with duck-typed counter / gauge /
  histogram interfaces
- `IAIso::Observability::OtelSpanSink` with duck-typed tracer / span
- `IAIso::Conformance::Runner` — vector runner exposed to both the
  Minitest conformance suite and the CLI subcommand
- `iaiso` admin CLI (`exe/iaiso`) — policy, consent, audit,
  coordinator, conformance subcommands

### Tested
- 54 unit tests with 109 assertions, 0 failures, 0 errors
- 67/67 conformance vectors passing (pressure 20/20, consent 23/23,
  events 7/7, policy 17/17)
- Cross-language JWT verification confirmed: a token signed by
  another reference SDK (loaded from `spec/consent/vectors.json`)
  verifies cleanly through this port's `Verifier`
- RSA roundtrip test: 2048-bit key signs a token, JWKS loads with
  `set_jwks_from_bytes`, verification succeeds

### Open items
- SIEM-vendor sinks (Splunk / Datadog / Loki / Elasticsearch ECS /
  Sumo / New Relic) deferred to 0.2.0. Use `JSONLFileSink` with a
  forwarder, or implement a sink in two methods (any object with
  `emit(event)`).
- YAML policies not supported in 0.1.0. Convert YAML to JSON
  externally.
