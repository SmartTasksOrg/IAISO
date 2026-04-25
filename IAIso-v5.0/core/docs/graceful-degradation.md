# Graceful Degradation Playbook

What happens when something IAIso depends on is down, and what you
should have configured to make that something-down event a non-crisis.

## Failure modes at a glance

| Failed dependency | Default behavior | Recommended configuration |
|---|---|---|
| SIEM endpoint (Splunk, Datadog, …) | Events are queued; if queue fills, events drop silently | Alert on `iaiso_sink_dropped_total`; consider `JSONLSink` + shipper |
| Redis (distributed coordinator) | `update()` raises an exception | Fallback to single-process; or fail-closed if your threat model demands |
| Redis (revocation list) | Fail-open or fail-closed, per `FailMode` | Fail-closed for high-trust scopes, fail-open otherwise |
| OIDC provider (during verification) | `OIDCError` raised | Fall back to previously-issued IAIso tokens; or reject new sessions |
| LLM provider | Call raises; pressure is not incremented; agent is stuck | Circuit breaker (`iaiso.reliability.CircuitBreaker`) |

## Policy 1: SIEM down

### Default

Webhook-based SIEM sinks (`SplunkHECSink`, `DatadogSink`, etc.) use an
in-process queue. When the queue fills:

- Further events are dropped, not blocked.
- The metric `iaiso_sink_dropped_total{sink=...}` increments.
- The audit event `audit.sink.dropped` is emitted to other sinks in a
  `FanoutSink` (if configured).

This is the right default for availability: a SIEM outage should not
take your agents down.

### When to override

- **Regulated environments** where every event must reach durable
  storage. Replace the webhook sink with a local `JSONLSink` on a
  reliable volume, and run a separate shipper (Fluent Bit, Vector,
  Splunk UF) that pushes from disk to the SIEM. This decouples your
  agent process from SIEM reliability.
- **Critical audit trails** that must be durable but can tolerate
  agent pauses. Override `WebhookSink._flush()` to block on
  queue-full instead of dropping.

### Detection

```
iaiso_sink_dropped_total > 0  →  P3 alert
iaiso_sink_dropped_total rate > 10/sec for 5 min  →  P1 alert
```

## Policy 2: Redis coordinator unreachable

### Default

`RedisCoordinator.update()` lets connection exceptions propagate.
Agents that don't handle the exception will crash on the next
pressure update. That's usually wrong — a Redis blip should not take
down every agent.

### Recommended configuration

Wrap the coordinator in a try/except and fall back to the in-process
`SharedPressureCoordinator` on failure, *or* to no coordinator at all
if you accept losing fleet-level coordination temporarily:

```python
from iaiso.coordination import SharedPressureCoordinator
from iaiso.coordination.redis import RedisCoordinator
from iaiso.reliability import CircuitBreaker, CircuitBreakerOpen

redis_coord = RedisCoordinator(redis_client, ...)
local_coord = SharedPressureCoordinator(...)
breaker = CircuitBreaker(failure_threshold=3, cooldown_seconds=30.0)

def update_fleet_pressure(exec_id: str, pressure: float):
    try:
        return breaker.call(redis_coord.update, exec_id, pressure)
    except (CircuitBreakerOpen, ConnectionError):
        # Log, emit audit, fall back
        return local_coord.update(exec_id, pressure)
```

If your threat model requires fleet-level coordination for safety
(e.g., rate-limiting across tenants), fall back to **deny** instead:

```python
except CircuitBreakerOpen:
    raise ExecutionLocked("coordinator unavailable; pausing agent")
```

### Detection

- Redis probes from your infrastructure monitoring.
- `breaker.snapshot().state == "open"` periodically logged or exposed
  via metrics.

## Policy 3: Revocation-list backend unreachable

### Default

The revocation-list backends expose a `FailMode`:

- `FailMode.OPEN` (default): on backend error, treat tokens as not
  revoked. Keeps things running.
- `FailMode.CLOSED`: on backend error, treat all tokens as revoked.
  No new sessions until the backend is back.

### Recommended configuration

- Use `OPEN` for low-risk scopes (read-only tools, informational
  queries).
- Use `CLOSED` for high-risk scopes (account deletion, payment,
  administrative actions). Better to block for the duration of a
  Redis outage than to allow revoked tokens to continue working.
- If you need different policies per scope, issue tokens against
  different backend instances configured separately.

### Detection

Check for repeated `consent.revocation.backend_error` audit events.

## Policy 4: OIDC provider unreachable

### Default

`OIDCVerifier.verify()` raises `OIDCNetworkError` or `OIDCError` on
any failure (discovery doc fetch, JWKS fetch, signature check).

### Recommended configuration

- **Primary path**: mint a short-lived IAIso consent token
  (`issue_from_oidc`) at session start, use the IAIso token for the
  rest of the session. This isolates agents from IdP downtime during
  an in-flight session.
- **Session start during IdP outage**: reject new sessions. Users see
  an auth failure, which is the correct response to an IdP outage.
- **JWKS caching**: `OIDCProviderConfig.jwks_cache_seconds` is 10 min
  by default. Raise to 1 hour if your IdP frequently flaps and you
  can tolerate slower key-rotation uptake.

## Policy 5: LLM provider down or rate-limited

### Default

The LLM call raises; the middleware does not record a step (since
there's nothing to count). The agent is stuck on that turn.

### Recommended configuration

Wrap LLM calls in a `CircuitBreaker`:

```python
from iaiso.reliability import CircuitBreaker, CircuitBreakerOpen

cb = CircuitBreaker(failure_threshold=5, cooldown_seconds=60.0)

def call_llm(messages):
    try:
        return cb.call(client.messages.create, model="...", messages=messages)
    except CircuitBreakerOpen:
        return fallback_canned_response()
```

For rate-limit-specific backoff, use `retry_after_seconds(engine)` to
tell the caller how long to wait.

## General principle

Every dependency IAIso touches either:

1. **Fails open.** Agent keeps running; operator gets alerted.
2. **Fails closed.** Agent stops; operator gets paged.
3. **Circuit-breaks.** Short-circuits retries during an outage;
   recovers automatically.

Pick your poison per dependency per threat model. IAIso does not
impose a single answer; it provides the primitives for you to choose.
