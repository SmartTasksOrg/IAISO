# SDK Scope and Architecture

IAIso's SDK is the runtime layer of a multi-layer safety architecture.
This document describes where the SDK's boundaries lie and how it
composes with the adjacent layers specified in the framework at
[`../../vision/`](../../vision/). Each section below makes the
composition explicit so operators can design complete systems that use
IAIso together with process isolation, hardware anchors, identity
providers, and observability platforms.

## Runtime boundaries

### SDK runs in the agent process

The SDK is a Python library that executes inside the agent's Python
process. This design keeps the hot path fast (sub-microsecond per step)
and makes integration a `pip install` away. Process-level compromise
containment is provided by the surrounding architecture: seccomp
profiles, separate UIDs, containers, gVisor/Firecracker sandboxes, or
VM boundaries. The framework's Layer 0 specifies these anchor points
— see [`../../vision/docs/spec/02-framework-layers.md`](../../vision/docs/spec/02-framework-layers.md)
and [`../../vision/docs/spec/06-layers.md`](../../vision/docs/spec/06-layers.md).

### Hardware-level anchors compose from outside the SDK

BIOS kill-switches, hypervisor FLOP caps, and cryptographic attestation
are specified by the framework at Layer 0. The SDK integrates with
those anchors through configuration — for example, `PRESSURE_THRESHOLD`
can be derived from a hardware-enforced compute quota rather than set
in a Python constant. Reference designs for hardware integration live
in [`../../vision/systems/hardware/`](../../vision/systems/hardware/)
(Intel, AMD, NVIDIA, ARM).

### Python is the reference language; ports are roadmap

The shipping SDK is Python. The normative specification in `../spec/`
is language-agnostic. Conformance vectors (67 machine-verifiable tests)
define the contract any port must pass. See [`CONFORMANCE.md`](CONFORMANCE.md)
for the porting workflow. Ports into Node.js, Go, Rust, and Java are
prioritized on the roadmap; see [`../CHANGELOG.md`](../CHANGELOG.md).

## Calibration boundaries

### Default coefficients are starting points, not workload-specific tuning

`PressureConfig` defaults — `token_coefficient=0.015`,
`tool_coefficient=0.08`, etc. — produce reasonable behavior on the
reference scenarios in `evals/`. For defensible thresholds on a
specific workload, run the calibration harness (`iaiso.calibration`)
with trajectories recorded from your actual agents and benchmarks.
See [`calibration.md`](calibration.md) for the methodology.

### Benchmark numbers in `bench/` are single-process microbenchmarks

They establish that the SDK is not the bottleneck in a realistic agent
loop. Throughput under concurrent load on production hardware is a
separate measurement — run the benchmark on your infrastructure and
pair it with a load test at deployment-scale concurrency.

### The SWE-bench / GAIA calibration infrastructure ships with the SDK

`scripts/record_swebench.py` and `scripts/record_gaia.py` implement
the recording pipeline. Running them requires real API access (OpenAI,
Anthropic, or your provider) and compute time to produce a calibrated
coefficient set for your deployment. The infrastructure ships; the
recordings are produced by the operator or researcher running the
study.

## Distributed-coordination architecture

### Redis-backed coordinator is shipping; additional consensus layers on roadmap

The `RedisCoordinator` uses atomic Lua scripts for multi-process fleet
coordination. Redis's consistency model is well-matched to aggregate
pressure updates. An etcd-backed coordinator is on the roadmap for
deployments that prefer Raft-based consensus; the interface is the
same six-method contract so both backends are interchangeable.

### Callbacks fire per-process; fleet-wide fanout uses the audit stream

When aggregate fleet pressure crosses an escalation threshold,
processes that observe the transition fire their own `on_escalation`
callback. For "every worker reacts to every transition" semantics,
subscribe to the coordinator's audit event stream via a SIEM fanout —
the audit path is the authoritative global signal.

### Coordinator TTL controls stale-state eviction

The Redis coordinator expires pressure values after
`pressures_ttl_seconds` (default 5 minutes). If a worker dies silently
and no other worker updates within that window, the dead worker's
pressure contribution is evicted. Operators running workloads where
workers legitimately sleep longer than the default should raise the
TTL.

## Audit delivery architecture

### Default audit delivery is best-effort with observable drops

Webhook sinks use bounded queues. Under sustained backpressure (SIEM
endpoint down, network slow), events are dropped rather than blocking
the agent, and `iaiso_sink_dropped_total` surfaces this in metrics —
point an alert at it.

For regulated environments where every event must reach durable
storage, two patterns work well:

1. Use `JSONLSink` to a local file on a durable volume with a separate
   shipper process (Fluent Bit, Vector). This decouples agent uptime
   from SIEM reliability and gives at-least-once delivery via the
   shipper.
2. Subclass `WebhookSink` to block on queue-full instead of dropping.
   This prioritizes durability over availability; choose per workload.

### SIEM sinks are verified against vendor-documented wire formats

Each sink's test suite validates that it produces the payload the
vendor documents (HTTP Event Collector for Splunk, Logs intake for
Datadog, etc.). End-to-end verification against a live ingest endpoint
is the first integration task for an operator adopting a particular
sink; it's typically a 30-minute exercise.

## Consent-token architecture

### Revocation is eventually consistent

Agents that have already cached a verified `ConsentScope` will see a
Redis revocation list update at their next re-verify. Operators choose
between re-verifying on every use (costs ~30µs per call for HS256) or
keeping TTLs short (minutes rather than hours).

### Tokens are signed; `metadata` is signed-but-readable

Consent tokens are JWTs: base64-encoded, signed, readable by anyone
who captures a token. Subject, scopes, and `jti` are designed to be
visible in audit trails. Place secrets outside the `metadata` field.
Encryption (JWE) is on the roadmap for workloads that need it.

## Integration architecture

### Middleware operates at the SDK's public API

Middleware for Anthropic, OpenAI, LangChain, LiteLLM, Gemini, Bedrock,
Mistral, and Cohere wraps the provider's SDK at its public-call
boundary. Internal retry-on-rate-limit paths inside a single
`.create()` call are counted as one logical call; wire up custom
accounting via the provider's callback hooks if finer granularity is
needed.

### Self-hosted LLM endpoints use token-based accounting by default

The self-hosted integration counts tokens as reported by the model
server. For compute-bound workloads (long context, heavy decoding),
pair token counting with explicit `record_step(tool_calls=...)`
accounting or extend `PressureConfig` with a compute-aware cost model.

### Scope boundaries: executions vs. accounts

IAIso constrains individual executions via pressure and fleet-level
runs via the coordinator. Account-level quotas ("user X is capped at
Y executions/day") are an identity-layer concept handled at the API
gateway or identity provider. See
[`../../vision/systems/identity/`](../../vision/systems/identity/) for
reference designs.

## Composition with adjacent safety layers

### Compliance certification

Certifications such as SOC 2 Type II, ISO 27001, EU AI Act, GDPR, and
HIPAA attach to audited organizational deployments, performed by
third-party auditors against a specific operational context. The SDK
produces the audit artifacts — event streams, signed consent records,
policy documents — that support the evidence requirements of those
audits. The certification itself is performed by the operator and
their auditors. See [`../../vision/docs/spec/12-regulatory.md`](../../vision/docs/spec/12-regulatory.md)
for the framework's standard-by-standard mapping.

### Prompt-injection defenses

IAIso constrains what an agent can do once it starts operating;
prompt-injection defenses constrain what reaches the agent in the
first place. These are complementary layers in a defense-in-depth
posture. Pair IAIso with input-sanitization, prompt-shielding, and
content-moderation systems at the ingress path.

### Agent correctness evaluation

IAIso counts tokens, tool calls, and planning depth — the mechanical
signals of execution cost. Semantic correctness of an agent's output
is an adjacent concern typically addressed by output validation,
test-time evaluation harnesses, and human review. The framework's
Layer 4 escalation bridge is the designed handoff point between
IAIso's mechanical signals and correctness-review workflows.

## Operational support model

- **Issue tracking and community support:** via GitHub Issues and
  Discussions.
- **Enterprise support:** commercial arrangements for 24/7 response,
  dedicated integration support, and compliance-audit assistance are
  available through `enterprise@iaiso.org`.
- **Deployment readiness:** calibrate thresholds, measure behavior,
  and run shadow/canary rollouts before placing the SDK in the
  enforcement path of a regulated workflow. See
  [`shadow-canary-mode.md`](shadow-canary-mode.md) for the recommended
  three-phase rollout.
