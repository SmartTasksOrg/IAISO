# Changelog

All notable changes to IAIso are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); version
numbering follows the policy in `docs/BACKWARDS_COMPATIBILITY.md`.

## [Unreleased]

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

Initial public release. This version replaces a prior prototype whose
documentation made claims the code did not support; every feature
listed here has corresponding tests in the repository.

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
- `docs/known-limitations.md`: explicit list of what IAIso does not
  do and does not claim to do.
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
