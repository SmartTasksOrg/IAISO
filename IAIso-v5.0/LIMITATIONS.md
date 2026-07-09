# Limitations

**Read this before you deploy IAIso in an enforcement path.**

IAIso is safety software. A buyer evaluating safety software needs to
find, in one place, what it fails to protect against. That is what this
document is for. The architecture material that follows the threat model
explains *why* the boundaries fall where they do — but the boundaries are
stated first, plainly, and without reframing.

- **Framework:** IAIso 5.0
- **SDK:** 0.2.0
- **Status:** beta

---

## 1. Threat model

| Adversary | Capability | IAIso's posture |
|---|---|---|
| Cooperating agent, buggy | Infinite tool loop, token flood, deep planning recursion | **Contained.** Engine locks at release threshold. |
| Cooperating agent, prompt-injected | Attacker-controlled text steers tool calls | **Partially.** Pressure bounds *volume*, not *intent*. Scope gates bound *reach*. Pair with input sanitization — IAIso has no classifier. |
| Agent with code execution in its own process | Monkeypatch `record_step`, catch `ExecutionLocked`, skip `.check()` | **NOT contained.** In-process enforcement is cooperative. Requires a Layer 0 out-of-process anchor. |
| Compromised host | Read `.iaiso_signing_key`, forge consent tokens | **NOT contained** under HS256 (symmetric). Use RS256 so the verifier holds only the public key. |
| Malicious operator | Set `token_coefficient=0`, `post_release_lock=false` | **NOT contained** by design. Policy is trusted input. Sign and review policy files. `enforcement_mode: strict` refuses to boot on some of these, but an operator who can edit the policy can also set the mode. |

### What the table means in practice

The SDK runs *inside* the agent process. It bounds a **cooperating**
agent: one that calls the middleware and honors `ExecutionLocked`. An
agent that can execute arbitrary code in that same process can reach in
and disable the thing that is supposed to bound it. There is no version
of in-process enforcement that survives an in-process adversary.

If your threat model includes an adversarial agent, IAIso's thresholds
must be bound to an out-of-process anchor: seccomp, a separate UID, a
container, a gVisor/Firecracker sandbox, a VM, or a hypervisor FLOP cap.
The framework calls this Layer 0. IAIso does not implement Layer 0; it
integrates with it. Deploying IAIso alone against an adversarial agent
is a configuration error, not a partial defense.

---

## 2. What IAIso does not know

**IAIso counts tokens, tool calls, and planning depth. It has no model of
*intent* or *correctness*. A cheap, correct-looking, catastrophic action
passes every check.**

One `DELETE FROM users` is one tool call. It costs almost nothing in
tokens and adds almost nothing to pressure. The pressure engine will not
notice, because there is nothing in the pressure engine that could
notice. Bound the *reach* of that action with a consent scope, and
validate its *correctness* somewhere else. Pressure is a rate limiter
with a good mental model, not a guardian.

**`ESCALATED` does not stop execution — it is a signal. Only `LOCKED`
refuses steps. An escalation delivered to a log nobody reads is not
human-in-the-loop.**

This is deliberate and it is preserved across every port; the
conformance vectors assert it. But it is also the classic
automation-complacency failure mode. If `on_escalation` writes to a log
file, IAIso has not put a human in the loop. It has put a line in a log.
Wire escalation to something that pages a person, or accept that the
only real stop in the system is `LOCKED`.

**Default coefficients are placeholders. Thresholds that have not been
calibrated against your workload will either never fire or fire
constantly.**

`token_coefficient=0.015`, `tool_coefficient=0.08`,
`depth_coefficient=0.05` are round numbers that behave sensibly on the
reference scenarios in `evals/`. They are not derived from your agents.
Under `enforcement_mode: strict` the SDK refuses to boot on uncalibrated
defaults without a calibration artifact, precisely because shipping
these numbers unexamined is the most common way to deploy IAIso and get
nothing from it.

**Audit delivery via `WebhookSink` is best-effort and drops under
backpressure. Alert on `iaiso_sink_dropped_total`. For regulated
workloads use `JSONLSink` + a shipper.**

A slow SIEM endpoint must not stall the agent, so the webhook sink drops
events rather than blocking. Dropped audit events are missing evidence.
If your compliance story depends on the audit trail being complete, do
not depend on `WebhookSink`.

---

## 3. Runtime boundaries

### The SDK runs in the agent process

This design keeps the hot path fast (sub-microsecond per step) and makes
integration one package install away. Process-level compromise
containment is provided by the surrounding architecture: seccomp
profiles, separate UIDs, containers, gVisor/Firecracker sandboxes, or VM
boundaries. The framework's Layer 0 specifies these anchor points — see
[`vision/docs/spec/02-framework-layers.md`](vision/docs/spec/02-framework-layers.md)
and [`vision/docs/spec/06-layers.md`](vision/docs/spec/06-layers.md).

Restating §1 because it is the fact most often skipped: an agent with
code execution in its own process is **not contained** by anything in
this repository.

### Hardware-level anchors compose from outside the SDK

BIOS kill-switches, hypervisor FLOP caps, and cryptographic attestation
are specified by the framework at Layer 0. The SDK integrates with those
anchors through configuration — for example, a pressure threshold can be
derived from a hardware-enforced compute quota rather than set in a
constant. Reference designs live in
[`vision/systems/hardware/`](vision/systems/hardware/).

### Python is the reference implementation

The normative specification in [`core/spec/`](core/spec/) is
language-agnostic, and 72 machine-verifiable conformance vectors (spec 1.1)
define the contract any port must pass. Ports that have not been run against
those vectors in a given build are marked as such in the port matrix in
[`README.md`](README.md). A port that does not pass every vector for the
spec version it claims is not a port.

## 4. Calibration boundaries

### Default coefficients are starting points

For defensible thresholds on a specific workload, run the calibration
harness (`iaiso.calibration`) with trajectories recorded from your actual
agents and benchmarks. See [`core/docs/calibration.md`](core/docs/calibration.md).

### Benchmark numbers in `bench/` are single-process microbenchmarks

They establish that the SDK is not the bottleneck in a realistic agent
loop. Throughput under concurrent load on production hardware is a
separate measurement — run the benchmark on your infrastructure and pair
it with a load test at deployment-scale concurrency.

### The calibration infrastructure ships; the recordings do not

`scripts/record_swebench.py` and `scripts/record_gaia.py` implement the
recording pipeline. Running them requires real API access and compute
time to produce a calibrated coefficient set for your deployment. The
infrastructure ships; the recordings are produced by the operator or
researcher running the study.

## 5. Distributed-coordination architecture

### Redis-backed coordinator is shipping; additional consensus layers are roadmap

The `RedisCoordinator` uses atomic Lua scripts for multi-process fleet
coordination. Redis's consistency model is well-matched to aggregate
pressure updates. An etcd-backed coordinator is on the roadmap for
deployments that prefer Raft-based consensus; the interface is the same
contract, so both backends are interchangeable.

### Callbacks fire per-process; fleet-wide fanout uses the audit stream

When aggregate fleet pressure crosses an escalation threshold, processes
that observe the transition fire their own `on_escalation` callback.
Callbacks are **not** exactly-once across the fleet. For "every worker
reacts to every transition" semantics, subscribe to the coordinator's
audit event stream — the audit path is the authoritative global signal.

### Coordinator TTL controls stale-state eviction

The Redis coordinator expires pressure values after
`pressures_ttl_seconds` (default 5 minutes). If a worker dies silently
and no other worker updates within that window, the dead worker's
pressure contribution is evicted. Operators running workloads where
workers legitimately sleep longer than the default should raise the TTL.

## 6. Audit delivery architecture

### Default webhook delivery is best-effort with observable drops

Webhook sinks use bounded queues. Under sustained backpressure (SIEM
endpoint down, network slow), events are dropped rather than blocking the
agent, and `iaiso_sink_dropped_total` surfaces this in metrics — point an
alert at it.

For regulated environments where every event must reach durable storage,
two patterns work:

1. Use `JSONLSink` to a local file on a durable volume with a separate
   shipper process (Fluent Bit, Vector). This decouples agent uptime from
   SIEM reliability and gives at-least-once delivery via the shipper.
2. Subclass `WebhookSink` to block on queue-full instead of dropping.
   This prioritizes durability over availability; choose per workload.

### SIEM sinks are verified against vendor-documented wire formats

Each sink's test suite validates that it produces the payload the vendor
documents (HTTP Event Collector for Splunk, Logs intake for Datadog, and
so on). End-to-end verification against a live ingest endpoint is the
first integration task for an operator adopting a particular sink.

## 7. Consent-token architecture

### HS256 gives the verifier the power to forge

Under HS256 the signing key and the verification key are the same bytes.
Any host that can verify a consent token can also mint one. A compromised
host is **not contained** under HS256. Use RS256 in any deployment where
the verifier is not the issuer, so the verifier holds only the public
half.

Under `enforcement_mode: strict` the SDK refuses to boot with an
auto-generated HS256 key, because nothing outside the process could ever
verify what it signs — the consent gate would be authorising only itself.

### Revocation is eventually consistent

Agents that have already cached a verified `ConsentScope` will see a
revocation-list update at their next re-verify. Operators choose between
re-verifying on every use (roughly 30µs per call for HS256) or keeping
TTLs short. The in-memory `RevocationList` shipped with each SDK is
process-local: it revokes nothing for the other twenty workers. Back it
with Redis or an equivalent shared store.

### Tokens are signed; `metadata` is signed-but-readable

Consent tokens are JWTs: base64-encoded, signed, readable by anyone who
captures one. Subject, scopes, and `jti` are designed to be visible in
audit trails. Place secrets outside the `metadata` field. Encryption
(JWE) is on the roadmap for workloads that need it.

## 8. Integration architecture

### Middleware operates at the SDK's public API

Middleware for Anthropic, OpenAI, LangChain, LiteLLM, Gemini, Bedrock,
Mistral, and Cohere wraps the provider's SDK at its public-call boundary.
Internal retry-on-rate-limit paths inside a single `.create()` call are
counted as one logical call; wire up custom accounting via the provider's
callback hooks if finer granularity is needed.

### Self-hosted LLM endpoints use token-based accounting by default

The self-hosted integration counts tokens as reported by the model
server. For compute-bound workloads (long context, heavy decoding), pair
token counting with explicit `record_step(tool_calls=...)` accounting or
extend the pressure config with a compute-aware cost model.

### Cost tracking is a readout, not a control

`model_costs` and `spend_usd` report what an execution cost. Pressure —
not spend — is the safety control. When `budget_usd` is exceeded, the
engine reuses the existing lock path rather than introducing a new
lifecycle state, so the wire format stays frozen. Spend is denominated in
prices you configured; if those prices are stale, so is the report.

### Scope boundaries: executions vs. accounts

IAIso constrains individual executions via pressure and fleet-level runs
via the coordinator. Account-level quotas ("user X is capped at Y
executions/day") are an identity-layer concept handled at the API gateway
or identity provider. See [`vision/systems/identity/`](vision/systems/identity/).

## 9. Composition with adjacent safety layers

### Compliance certification

Certifications such as SOC 2 Type II, ISO 27001, EU AI Act, GDPR, and
HIPAA attach to audited organizational deployments, performed by
third-party auditors against a specific operational context. The SDK
produces the audit artifacts — event streams, signed consent records,
policy documents — that support the evidence requirements of those
audits. The certification itself is performed by the operator and their
auditors. See [`vision/docs/spec/12-regulatory.md`](vision/docs/spec/12-regulatory.md).

IAIso being present in a deployment is not evidence of compliance. The
event stream it produces might be.

### Prompt-injection defenses

IAIso constrains what an agent can do once it starts operating;
prompt-injection defenses constrain what reaches the agent in the first
place. These are complementary layers. IAIso ships no classifier and
makes no attempt to detect injected instructions. Pair it with
input-sanitization, prompt-shielding, and content-moderation systems at
the ingress path.

### Agent correctness evaluation

Semantic correctness of an agent's output is an adjacent concern,
typically addressed by output validation, test-time evaluation harnesses,
and human review. The framework's Layer 4 escalation bridge is the
designed handoff point between IAIso's mechanical signals and
correctness-review workflows — and, per §2, that handoff is only as real
as the thing on the other end of it.

## 10. Operational support model

- **Issue tracking and community support:** GitHub Issues and Discussions.
- **Enterprise support:** commercial arrangements for 24/7 response,
  dedicated integration support, and compliance-audit assistance are
  available through `enterprise@iaiso.org`.
- **Deployment readiness:** calibrate thresholds, measure behavior, and
  run shadow/canary rollouts before placing the SDK in the enforcement
  path of a regulated workflow. See
  [`core/docs/shadow-canary-mode.md`](core/docs/shadow-canary-mode.md)
  for the recommended three-phase rollout.
