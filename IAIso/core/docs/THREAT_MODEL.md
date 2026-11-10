# IAIso Threat Model

Last updated: 2026-04-23. This document is versioned; material changes
bump the "Version" line below and appear in CHANGELOG.md.

Version: 0.1.0

## Scope

This threat model covers the IAIso library and the reference
deployment templates in `deploy/`. It does **not** cover:

- The LLM provider API that a wrapped agent calls. Trust and threat
  assumptions for that provider are the user's responsibility.
- The agent application code itself. IAIso constrains what an agent
  can do; it does not reason about what the agent's prompts say.
- The hosting infrastructure (cloud VPC, node isolation, etc.).

## Assets

The things an attacker might want to compromise:

1. **Pressure state integrity.** If an attacker can force pressure to
   stay below threshold for an agent that should have been stopped,
   IAIso's safety property is broken.
2. **Consent tokens.** Forgeable tokens allow unauthorized agents to
   run or access scoped tools.
3. **Audit log integrity.** Tampered audit logs allow incidents to be
   hidden from investigators.
4. **Policy configuration.** Replacing `policy.yaml` with permissive
   values silently widens the blast radius.
5. **Coordinator shared state (Redis).** Corrupting shared pressure
   values affects the entire fleet.

## Adversaries

We model four adversary classes:

- **A1: Malicious end-user** who sends crafted prompts to the agent.
  Cannot execute code on the host; can only influence agent behavior
  through model inputs.
- **A2: Compromised agent process.** Arbitrary code execution inside
  the process that hosts IAIso. Has access to Python memory, local
  filesystem within the process's permissions, and network egress.
- **A3: Network adversary** positioned between IAIso and downstream
  services (Redis, SIEM, IdP). Can observe and tamper with traffic if
  TLS is misconfigured.
- **A4: Malicious operator / insider** with legitimate access to the
  deployment. Can change configuration, read secrets, alter audit
  logs at the storage layer.

## Trust boundaries

```
    ┌─────────────────────────────────────────────────────┐
    │  Agent process (IAIso lib + user code)              │
    │                                                      │
    │   agent code  ◄─► BoundedExecution ◄─► PressureEngine│
    │                                                      │
    └──────────┬──────────────┬───────────────┬───────────┘
               │              │               │
         consent JWT       SIEM sink      Redis/coord
               │              │               │
               ▼              ▼               ▼
    ┌──────────────┐  ┌─────────────┐  ┌──────────────┐
    │ IdP (OIDC)   │  │ SIEM vendor │  │ Redis (shared│
    │ Okta/Auth0…  │  │ Splunk/etc. │  │ pressure)    │
    └──────────────┘  └─────────────┘  └──────────────┘
```

The agent process is NOT trusted to be free of compromise. If A2 lands
inside the agent, IAIso's in-process state is exposed; the useful
properties are those preserved by downstream systems (audit log, Redis
state).

## Threat catalog and mitigations

### T1 — A1 drives pressure high enough to exhaust a resource

_Scenario:_ A user crafts prompts that cause the agent to loop,
generating many steps per second, overwhelming the audit sink.

_Mitigation:_ PressureEngine is designed to escalate well before CPU
or memory is saturated; the audit sink uses bounded queues
(`max_queue_size` on `WebhookConfig`) that drop events under
backpressure rather than blocking. `iaiso_sink_dropped_total` surfaces
this in metrics.

_Residual:_ If the user controls the agent's actual downstream calls
(LLM, tools), they can still consume budget / provider quota.
IAIso does not address per-provider quota.

### T2 — A1 makes the agent call a tool outside its consent scope

_Scenario:_ A user asks an agent to run a tool the agent was not
consented for (e.g., "send email to everyone").

_Mitigation:_ `BoundedExecution.require_scope(scope)` raises
`ConsentScopeError` when the scope is not in the token. Tool wrappers
that call `require_scope()` before invoking the tool catch this.

_Residual:_ If the tool itself is unwrapped, IAIso cannot stop it.
Users must instrument tool invocations, ideally in a central router.

### T3 — A2 mutates PressureEngine state

_Scenario:_ Compromised code inside the agent process directly mutates
`engine._pressure` to 0.

_Mitigation:_ Minimal. Python's runtime model does not prevent this.
IAIso relies on the coordinator's shared state (Redis) for fleet-level
correctness: even if one process lies about its own pressure, the
coordinator sees only what that process reports.

_Residual:_ A compromised process can report false pressures to the
coordinator. Detection: diff per-process reported pressure against
independent signals (LLM-provider usage logs, network egress metrics).

### T4 — A3 intercepts audit events in flight

_Scenario:_ TLS interception on the path between IAIso and Splunk/
Datadog/Elastic.

_Mitigation:_ All SIEM sinks default to `verify_tls=True` and require
HTTPS. Authentication tokens (Splunk HEC, New Relic API-Key, etc.)
are sent in headers, not URLs.

_Residual:_ If the operator deliberately disables `verify_tls`,
defense is lost. This should generate an alert at deploy time, which
is the operator's responsibility.

### T5 — A3 tampers with Redis traffic

_Scenario:_ Network adversary between the coordinator workers and
Redis.

_Mitigation:_ redis-py supports `rediss://` (TLS) and AUTH. The
Redis coordinator passes through whatever client the caller
provides; we do not downgrade. The Helm chart documents Redis auth
via Secret reference.

_Residual:_ If Redis itself is compromised, the attacker sees all
fleet pressures and can manipulate them. Fail-closed behavior for
critical agents (refuse to run if coordinator is unreachable) is the
operator's choice via the `on_coordinator_error` hook.

### T6 — Consent token forgery

_Scenario:_ A2 or A4 tries to mint a token with unauthorized scopes.

_Mitigation:_ ConsentScope tokens are signed (HS256 symmetric or
RS256 asymmetric). Verification requires the key; for RS256, the
signing key can live outside the agent process entirely. Revocation
lists support real-time invalidation.

_Residual:_ If the signing key is exposed (A2 reads it from memory,
A4 reads it from config), full compromise. For RS256 deployments with
the signing key in an HSM/KMS and only the public key in agents, this
threat is mitigated even against A2.

### T7 — Policy tampering

_Scenario:_ A4 modifies `policy.yaml` to raise thresholds or disable
escalation.

_Mitigation:_ The Helm chart mounts the ConfigMap read-only. The
policy-as-code loader validates values at load time. Changes to the
ConfigMap appear in Kubernetes audit logs if enabled.

_Residual:_ A4 with cluster-admin rights can modify the ConfigMap.
Detection requires Kubernetes audit logs being forwarded to a separate
trust domain.

### T8 — Replay attacks against consent tokens

_Scenario:_ An attacker who captures a valid token replays it after
it should have been invalidated.

_Mitigation:_ Tokens have `exp` claims. Revocation lists support
early invalidation (`RevocationList.revoke(jti)`). The `jti` claim
is unique per token.

_Residual:_ Within the window before `exp`, a captured token is
usable unless revoked. Shorter TTLs reduce this window at the cost of
more frequent re-minting.

### T9 — Audit log tampering at rest

_Scenario:_ A4 deletes or modifies audit records in the SIEM.

_Mitigation:_ Out of IAIso's scope. IAIso produces correct events;
preserving them is the SIEM's job. Use write-only audit destinations
(S3 Object Lock, Splunk indexer with RBAC preventing delete) where
available.

### T10 — Denial of service via coordinator contention

_Scenario:_ Large fleet with high update rate causes Redis contention
and slow escalation decisions.

_Mitigation:_ The Redis coordinator uses a single Lua script per
update (atomic read-modify-write), which is fast. Benchmark before
deploying fleets above ~1000 workers. The `notify_cooldown_seconds`
setting prevents callback storms.

_Residual:_ At very large scale, consider sharded coordinators
(different `coordinator_id` per shard) or a different consensus
layer. An etcd-backed coordinator is on the roadmap; the interface is
the same six methods as the Redis backend.

## Secrets in scope

- Consent-token signing key (HS256 secret or RS256 private key).
- Redis AUTH password, if used.
- SIEM vendor tokens (Splunk HEC token, Datadog API key, etc.).
- OIDC provider API keys, if used for management-plane operations.

All secrets should be injected via environment variables or mounted
secret volumes — never baked into container images or policy files.

## Known weaknesses explicitly accepted

1. **Single-process compromise is not contained.** See T3 and T6.
   Process-level isolation (separate UIDs, seccomp, gVisor) reduces
   but does not eliminate this.
2. **Audit sinks are best-effort by default.** Backpressure drops
   events rather than blocking the agent. This is a deliberate
   availability-over-consistency choice; change `max_queue_size` and
   the flushing strategy for compliance-grade delivery.
3. **No end-to-end encryption of audit payloads.** Events are TLS-
   encrypted in transit and stored per the SIEM's at-rest policy.
   If you need tamper-evident audit, add signatures at the producer
   side; the fanout-sink pattern makes that straightforward.

## Out of scope

- Prompt injection and jailbreaks. Use a separate layer for that.
- Model-level hallucination containment. IAIso counts tool calls, not
  correctness.
- Physical security of agents. IAIso is a software library.

## Change process

Material changes to this threat model — new threats, new mitigations,
changes to residual risk statements — go through the normal PR process
and bump the version above.
