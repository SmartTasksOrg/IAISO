# IAIso

**Experimental framework for bounded agent execution.** IAIso is a Python library
that adds rate-limiting, scope-based authorization, and structured audit logging
to LLM agent loops. It is designed to be one component of a larger agent
architecture — not a complete safety solution.

> **Status:** Alpha (0.1.0). The core API is working and tested, but has not
> been deployed at scale. Do not rely on IAIso as the sole safeguard for
> high-stakes systems. See "What IAIso is not" below.

## What it does

Three things, each usable independently:

1. **Pressure-accumulation rate limiting.** A `PressureEngine` tracks a scalar
   "pressure" value that rises with tokens generated, tools called, and
   planning depth, and falls via configurable dissipation. When pressure
   crosses configurable thresholds, the engine signals escalation or forces
   a state reset. Unlike hard token or tool-call counters, a single pressure
   value can catch tool-loop runaways, token floods, AND deep planning
   spirals — but it requires calibration (see below).

2. **ConsentScope — signed, scoped, expiring authorization tokens.** Real
   JWTs (HS256 or RS256) with prefix-based scope matching, optional
   execution binding, explicit expiry, and an extensible revocation list.
   Gate sensitive operations behind `execution.require_scope("tools.admin")`.

3. **Structured audit events.** Every state change emits a versioned
   structured event to a pluggable sink. Ship to stdout, a JSONL file,
   a webhook (SIEM / log aggregator), or a fanout of all three.
   The event schema is normatively specified in [`spec/events/`](spec/events/)
   and is stable within a major version.

## Specification

IAIso ships a **normative, machine-checkable specification** in the
[`spec/`](spec/) directory:

- [`spec/pressure/`](spec/pressure/) — the pressure-accumulation model,
  with 20 hand-computed test vectors.
- [`spec/consent/`](spec/consent/) — JWT token format + scope grammar,
  with JSON Schema and 23 vectors.
- [`spec/events/`](spec/events/) — audit event envelope + per-kind
  payloads, with JSON Schema and 7 vectors.
- [`spec/policy/`](spec/policy/) — policy file format, with JSON Schema
  and 17 vectors.
- [`spec/coordinator/`](spec/coordinator/) — fleet-wide coordinator
  (Redis keyspace + DRAFT gRPC wire format).

The Python package is a reference implementation that passes every
vector. See [`docs/CONFORMANCE.md`](docs/CONFORMANCE.md) for a workflow
guide on porting IAIso to another language (Node, Go, Rust, Java, …).

Run the conformance suite:

```bash
python -m iaiso.conformance spec/
# or, as pytest cases:
pytest tests/test_conformance.py -v
```

## Install

```bash
pip install iaiso
```

Optional extras for LLM SDK integrations and backends:

```bash
# LLM middleware
pip install iaiso[anthropic]   # Anthropic SDK
pip install iaiso[openai]      # OpenAI SDK (+ OpenAI-compatible servers)
pip install iaiso[langchain]   # LangChain callback handler
pip install iaiso[litellm]     # LiteLLM wrapper (100+ providers)
pip install iaiso[gemini]      # Google Gemini / Vertex AI
pip install iaiso[bedrock]     # AWS Bedrock Runtime
pip install iaiso[mistral]     # Mistral
pip install iaiso[cohere]      # Cohere

# Backends and integrations
pip install iaiso[redis]       # Redis coordinator and revocation list
pip install iaiso[metrics]     # Prometheus exposition
pip install iaiso[otel]        # OpenTelemetry metrics + tracing
pip install iaiso[policy]      # YAML policy files
pip install iaiso[oidc]        # OIDC token verification
```

For self-hosted LLM servers (vLLM, Ollama, TGI, SGLang, etc.), no
additional wrapper is needed — they expose OpenAI-compatible endpoints
and work with the OpenAI middleware. See `docs/self-hosted.md`.

## Minimal example

```python
from iaiso import BoundedExecution, PressureConfig, StepOutcome

with BoundedExecution.start(config=PressureConfig()) as exec_:
    for step in agent_loop():
        if exec_.check() is StepOutcome.ESCALATED:
            pause_for_human_review()
            break
        result = do_step(step)
        exec_.record_step(
            tokens=result.tokens,
            tool_calls=result.tool_calls,
            tag=step.name,
        )
```

A complete runnable example is in `examples/simulated_agent.py`. See
`docs/getting-started.md` for more patterns.

## Evaluation

The repository ships with an evaluation harness that compares IAIso against
baseline approaches (no limits, token budget, tool-call counter) on
adversarial scenarios. Run it yourself:

```bash
python -m iaiso.evaluation
```

Reference results from the default config on the shipped scenarios are in
`evals/baseline/summary.csv`. Summary of observed behavior:

| Scenario              | Expected | no-limit | token-budget | tool-counter | iaiso   |
|-----------------------|----------|----------|--------------|--------------|---------|
| benign-short          | pass     | pass     | pass         | pass         | pass    |
| mixed-realistic       | pass     | pass     | pass         | pass         | pass    |
| runaway-tool-loop     | catch    | miss     | miss         | catch        | catch early |
| token-flood           | catch    | miss     | catch best   | miss         | catch   |
| depth-bomb            | catch    | miss     | miss         | miss         | catch   |
| slow-creep            | —        | pass     | pass         | pass         | pass    |

Honest takeaways from the data:

- IAIso uniquely catches `depth-bomb` — none of the single-signal baselines do.
- IAIso catches tool-loop runaways earlier than a pure tool-call counter.
- **IAIso is worse than a strict token budget on pure token floods.** A token
  budget catches the flood at a known hard limit; IAIso catches it later
  because the release threshold takes longer to reach.
- Neither IAIso nor the baselines catch `slow-creep` at default settings.
  This is a calibration point: raise `dissipation_per_step` and you catch it
  at the cost of more false positives elsewhere.

The right approach for a given deployment likely **combines** multiple
signals. See `docs/calibration.md` for how to tune for your workload.

## What IAIso is not

Stating this explicitly because the previous version of this project
overclaimed substantially:

- **Not a safety guarantee.** It is a rate-limiting primitive. A compromised
  agent in the same process can bypass it. For stronger isolation, run
  agents in sandboxes and enforce at process boundaries.
- **Not a compliance product.** Running this library does not make a system
  compliant with the EU AI Act, GDPR, ISO 42001, or any other regulation.
  Compliance is an organizational property. IAIso may produce artifacts
  (event logs, signed consent records) that assist compliance work
  performed by other parties — it does not perform that work itself.
- **Not deployed at Fortune 500 / critical infrastructure / aerospace / biotech.**
  Past documentation made such claims; those were not accurate. This
  library is an early-stage project maintained by a small number of
  contributors.
- **Not hardware-enforced.** There is no BIOS-level integration, no
  air-gapped isolation, no cryptographic attestation. The engine is
  pure Python running in the agent's process.

## Additional subsystems

Built against real wire formats / protocols and covered by tests, but
requiring end-to-end verification in the target environment before
production use:

- **Cross-execution coordination** (`iaiso.coordination`). Fleet-wide
  pressure aggregation across multiple `BoundedExecution` instances.
  Pluggable aggregators (sum, mean, max, weighted-sum). See
  `docs/coordination.md`.
- **Redis-backed coordinator** (`iaiso.coordination.redis`). Multi-process
  fleet coordination using atomic Lua scripts. Tested via `fakeredis`;
  end-to-end verification against your real Redis is still required.
- **Redis-backed revocation list** (`iaiso.consent.backends`). Drop-in
  replacement for the in-memory `RevocationList`. Requires
  `pip install iaiso[redis]`.
- **SIEM audit sinks** — Splunk HEC, Datadog Logs, Elastic Common
  Schema, Sumo Logic HTTP Source, New Relic Logs, Grafana Loki.
  Verified against mock HTTP servers, not against live vendor
  instances. See `docs/siem.md`.
- **LLM middleware** — Anthropic, OpenAI (and OpenAI-compatible
  servers), LangChain, LiteLLM, Google Gemini / Vertex AI, AWS
  Bedrock (Converse API + invoke_model), Mistral, Cohere.
- **Metrics & tracing** (`iaiso.metrics`, `iaiso.observability.tracing`).
  Prometheus, OpenTelemetry (metrics and spans), plus an in-memory
  sink that renders Prometheus exposition format without external deps.
- **Policy-as-code** (`iaiso.policy`). Load `PressureConfig`,
  coordinator config, and consent policy from YAML or JSON files with
  inline schema validation. Includes `iaiso policy template`.
- **Admin CLI** (`iaiso.cli`). `python -m iaiso` with subcommands for
  policy validation, consent token issue/verify, audit-log tail and
  stats, and coordinator demo.
- **Reliability primitives** (`iaiso.reliability`). `CircuitBreaker`
  for downstream failures and `retry_after_seconds()` derived from
  pressure and dissipation rate.
- **OIDC identity** (`iaiso.identity`). Verify Okta / Auth0 / Azure AD
  access tokens via JWKS, map OIDC claims (`scp`, `groups`, `roles`)
  into IAIso scopes, optionally mint signed IAIso consent tokens from
  verified OIDC tokens.
- **Empirical calibration infrastructure** (`iaiso.calibration`,
  `scripts/record_*.py`, `scripts/run_calibration_study.py`). Record
  pressure trajectories from real agent runs, fit coefficients that
  separate benign from runaway behavior, validate on held-out runs.
  The infrastructure is in; the study itself is yours to run.
- **Performance microbenchmarks** (`iaiso.bench.microbench`). Single-
  process throughput numbers for all core primitives. See
  `bench/README.md` for what the numbers do and don't mean.
- **Deployment templates** (`deploy/`). Dockerfile + docker-compose
  for local dev, Helm chart with restricted PodSecurityContext and
  optional ServiceMonitor, Terraform module wrapping the chart.

## Operational guides

- `docs/THREAT_MODEL.md` — adversaries, assets, trust boundaries, and
  mitigation mapping.
- `docs/BACKWARDS_COMPATIBILITY.md` — versioning and deprecation policy.
- `docs/known-limitations.md` — explicit list of what IAIso does not do.
- `docs/graceful-degradation.md` — playbook for SIEM / Redis / OIDC /
  LLM provider outages.
- `docs/shadow-canary-mode.md` — recommended three-phase rollout
  (observe → log-only → enforce).
- `docs/CONTRIBUTING.md` — review bar beyond "tests must pass".
- `CHANGELOG.md` — structured release notes.

## Roadmap

Still open:

- **Empirical calibration results on public benchmarks.** Infrastructure
  is shipped; running against SWE-bench / GAIA / WebArena requires real
  API budget and is separate work this repo does not claim to have done.
- **Performance benchmarks at production scale.** The microbenchmark
  establishes single-process lower bounds. A real load test against
  a large fleet on production-grade hardware is separate work.
- **Third-party security audit.** The threat model and mitigations are
  documented; an independent review is still pending.
- **etcd-backed coordinator.** Redis covers most use cases; etcd is
  listed as future work for environments that prefer it.
- **LiteLLM proxy-mode integration.** Current middleware accounts at
  the Python library level; proxy-layer integration is separate work.

Completed in 0.1.0 (previously on the roadmap):

- ✅ Multi-process coordinator (Redis-backed).
- ✅ Prometheus / OpenTelemetry metrics export.
- ✅ Distributed tracing (OTel spans).
- ✅ Admin CLI for runtime operations.
- ✅ Policy-as-code (YAML/JSON).
- ✅ Deployment templates (Docker, Helm, Terraform).
- ✅ OIDC identity integration (Okta / Auth0 / Azure AD).
- ✅ SIEM diversity (Splunk, Datadog, Elastic, Sumo, New Relic, Loki).
- ✅ Broader middleware (Gemini, Bedrock, Mistral, Cohere, in addition
  to Anthropic, OpenAI, LangChain, LiteLLM).
- ✅ Circuit breaker and retry-after primitives.
- ✅ Threat model, backwards-compatibility policy, graceful-degradation
  playbook, shadow/canary rollout guide.

## Contributing

Issues and PRs welcome. Before proposing large changes, please open an
issue to discuss fit. Tests must pass (`pytest`) and new features should
come with tests and docs.

## License

Apache-2.0.
