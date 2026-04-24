# Known Limitations

A deliberately direct list of what IAIso does *not* do. If an
assumption listed here is wrong for your use case, you probably want
a different tool — or to extend IAIso with explicit awareness of the
gap.

## Architectural limits

### IAIso is an in-process library, not a sandbox.

It runs in the same Python process as your agent code. A compromised
agent with arbitrary code execution inside that process can read
consent tokens, mutate pressure state, and bypass everything IAIso
enforces. If you need compromise containment, run agents in isolated
processes (separate UIDs, seccomp profiles, VMs, or containers), and
use IAIso as one layer of a defense-in-depth stack.

### No hardware-level enforcement.

Earlier prototypes claimed "BIOS-level FLOP limits" and "air-gapped
isolation." These were not implementable as a Python library and have
been removed. If you need hardware enforcement, that's a kernel /
hypervisor / firmware problem, not one IAIso can solve.

### Single-language, Python-only.

IAIso is a Python library. Non-Python agents (Node.js, Go, Rust) can
only integrate via running a Python process or reimplementing the
wire formats (audit events, consent tokens, coordinator protocol).
We don't currently ship clients for other languages.

## Calibration limits

### Default pressure coefficients are not grounded in empirical data.

`PressureConfig` defaults — `token_coefficient=0.015`, `tool_coefficient=0.08`,
etc. — are reasonable starting points, not tuned values. To get
defensible thresholds for your workload, use the calibration harness
(`iaiso.calibration`) with trajectories recorded from your actual
agents and benchmarks.

### Benchmark numbers in `bench/` are single-process microbenchmarks.

They show the library is not the bottleneck in any realistic agent
loop, but they do not predict behavior under concurrent load on
production hardware. For that, run the benchmark on your hardware and
then do a real load test.

### The SWE-bench / GAIA calibration infrastructure ships empty.

`scripts/record_swebench.py` and `scripts/record_gaia.py` are
recorders that require real API access (OpenAI, Anthropic, or your
provider of choice) and real compute time to produce results. We
ship the recording infrastructure but not the recorded trajectories
themselves.

## Distributed-coordination limits

### The Redis coordinator's callbacks fire per-process, not globally.

When aggregate fleet pressure crosses the escalation threshold, only
processes that observe the transition in their local state fire their
own `on_escalation` callback. Processes that never call `update()`
between the transition and its reversal won't fire anything.

If you need "every worker reacts to every transition," subscribe to
the coordinator's audit events via a separate fanout, not via the
per-process callbacks.

### No etcd or Raft-based coordinator.

Only Redis is implemented for distributed coordination. Redis's
consistency model is sufficient for the aggregate-pressure use case;
stronger consistency (linearizable reads, strict serializability) is
not required for pressure aggregation and not provided.

### Coordinator TTL means stale state.

The Redis coordinator expires pressure values after
`pressures_ttl_seconds` (default 5 minutes). If a worker dies silently
and another worker doesn't update within that window, the dead
worker's pressure contribution is forgotten. This is usually what
you want — but if workers legitimately sleep for longer than the TTL,
raise the value.

## Audit limits

### Default audit delivery is best-effort.

Webhook sinks use bounded queues. Under sustained backpressure (SIEM
endpoint down, network slow), events are dropped rather than blocking
the agent. `iaiso_sink_dropped_total` surfaces this in metrics; use
it as an alert source.

For regulated environments where every event must reach durable
storage, either:
1. Use `JSONLSink` to a local file on an EBS volume with a separate
   shipper process (Fluent Bit, Vector), which decouples agent
   uptime from SIEM reliability.
2. Subclass `WebhookSink` to block on queue-full instead of dropping,
   accepting the availability trade-off.

### SIEM sinks have been wire-format-verified, not end-to-end verified.

Each sink's tests validate that we produce the payload the vendor
documents. We have not, for every vendor, exercised a live ingest
endpoint to confirm the data lands and renders correctly. This is
the first integration task for any user adopting a particular sink.

## Consent-token limits

### Revocation is eventually consistent.

If you revoke a token via a Redis revocation list, agents that already
cached the verified `ConsentScope` will not see the revocation until
they re-verify. Either re-verify on every use (costs ~30µs per call
for HS256) or keep TTLs short.

### Tokens are signed, not encrypted.

Consent tokens contain subject, scopes, and a jti in plaintext
(base64-encoded, but readable by anyone who captures a token). Don't
put secrets in the `metadata` field. If you need encrypted tokens,
use JWE; IAIso doesn't ship JWE support.

## Integration limits

### Middleware is wrap-only; it does not intercept internal SDK calls.

If an SDK makes nested requests we don't see — for example, a
retry-on-rate-limit that issues additional API calls inside one
logical `.create()` — we count that as one call, not the real number.
Most SDKs expose callbacks or hooks for this; check your SDK's docs
and wire up custom accounting if needed.

### Self-hosted LLM endpoints account for tokens, not compute.

Our self-hosted integration counts tokens as reported by the model
server. If your workload is compute-bound (long context, heavy
decoding), tokens underestimate real cost. Add custom
`record_step(tool_calls=...)` accounting or extend `PressureConfig`
with your own cost model.

### No per-agent quotas.

IAIso constrains individual executions via pressure and fleet-level
runs via the coordinator. It does not implement "user X is capped at
Y executions/day" — that's an account-level concept best handled at
the API-gateway or provider layer.

## Scope boundaries

### We are not a compliance product.

IAIso produces audit artifacts that compliance workflows can use.
IAIso itself is not certified against SOC 2, ISO 27001, EU AI Act,
GDPR, HIPAA, or any other framework. Certification applies to
organizations and deployments, not to libraries.

### We do not prevent prompt injection.

IAIso constrains what an agent can do, not what a user can type.
Prompt-injection defenses are a different layer; use them alongside
IAIso, not instead of.

### We do not evaluate agent correctness.

If an agent uses 500 tokens to write a buggy answer, IAIso is silent
about the buggy-ness. It counts tokens, tool calls, and planning
depth — not semantic quality. Correctness evaluation is its own hard
problem.

## Promises we explicitly don't make

- No SLA. This is a library; running it reliably is your job.
- No 24/7 support. Best-effort issue response only.
- No guarantee of fitness for any specific regulated use case.
- No guarantee that the defaults are correct for your workload.
  Calibrate, measure, and tune before depending on the numbers.
