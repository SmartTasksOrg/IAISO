# Shadow Mode and Canary Rollouts

Rolling out pressure-based enforcement in front of a live agent is a
lot like rolling out a rate limiter: if your thresholds are wrong,
you'll block traffic that shouldn't be blocked. Do it wrong and your
ops team will rip IAIso out at 3am.

This document describes the three-phase rollout we recommend:
**observe → log-only → enforce**, with the `PressureConfig` settings
for each.

## Phase 1: Observe (shadow mode)

**Goal**: gather data on what pressure your agents actually generate,
with zero risk of blocking real traffic.

**Configuration**: thresholds set above any plausible real value.

```python
config = PressureConfig(
    token_coefficient=0.015,
    tool_coefficient=0.08,
    escalation_threshold=10.0,   # way above the 0-1 range of real pressure
    release_threshold=10.0,
    post_release_lock=False,
)
```

At this configuration, `BoundedExecution` will never escalate,
release, or lock. Every step still emits audit events (so you can
analyze pressure distributions), and metrics update normally.

**What to watch**:
- `iaiso_pressure` gauge by execution — what's the distribution at
  p50, p95, p99?
- `iaiso_steps_total{outcome="escalated"}` — should be zero.
- Correlate high-pressure executions with actual bad behavior
  (looping agents, runaway tool spam). If they don't correlate, your
  coefficients are probably wrong.

**How long**: at least one week of production traffic. Longer for
workloads with business-hour effects.

**Exit criteria**: you have a defensible value for
`escalation_threshold` based on real observed pressure, and you've
decided what percentile of executions you're willing to escalate.

## Phase 2: Log-only mode (canary)

**Goal**: fire escalation hooks and callbacks, but do not block the
agent. If escalation is wrong, you see it in logs; if it's right,
you see that too.

**Configuration**: realistic `escalation_threshold`, but
`post_release_lock=False` and `release_threshold` high enough that
release doesn't happen.

```python
config = PressureConfig(
    token_coefficient=0.015,
    tool_coefficient=0.08,
    escalation_threshold=0.85,   # based on Phase 1 data
    release_threshold=10.0,      # effectively disabled
    post_release_lock=False,
)

def on_escalation(snapshot):
    # Log but do not act.
    logger.warning("would_escalate: pressure=%.3f", snapshot.pressure)
    metrics.increment("iaiso.would_escalate")

execution = BoundedExecution.start(
    config=config,
    on_escalation=on_escalation,
)
```

**What to watch**:
- `iaiso_escalations_total` — how often does escalation fire?
- Compare timestamps of escalations against user complaints,
  customer-success tickets, and agent-quality dashboards. Do
  escalations correlate with actual problems?
- False-positive rate: of N escalations, how many were for agents
  doing legitimate work?

**How long**: at least another week. You want to have seen every
quirky use case your agents encounter.

**Exit criteria**: escalation rate is acceptable (1-5% of sessions is
typical), the correlation with real problems is good, and you trust
the default callback behavior.

## Phase 3: Enforcing mode (production)

**Goal**: now IAIso actually protects.

**Configuration**: full enforcement with realistic values.

```python
config = PressureConfig(
    token_coefficient=0.015,
    tool_coefficient=0.08,
    escalation_threshold=0.85,
    release_threshold=0.95,
    post_release_lock=True,
)
```

**Deployment pattern**: ideally, start with a percentage of traffic
on the new config and ramp. If your deployment supports feature flags:

```python
if user_in_enforce_cohort(user_id, rollout_percent=5):
    config = enforcing_config
else:
    config = log_only_config
```

Ramp 5% → 25% → 50% → 100% over the course of a week, watching
complaint channels at each step.

**Rollback**: if things go wrong, flip the flag back to log-only. The
audit logs continue; users' agents keep running. No redeploy
required.

## Testing shadow mode in CI

You can exercise shadow mode in your CI regression suite by running
an agent's happy-path test with shadow config, and asserting the
audit log contains the pressure values you expect:

```python
def test_agent_pressure_stays_in_bounds():
    sink = MemorySink()
    with BoundedExecution.start(
        config=PressureConfig(
            escalation_threshold=10.0,  # shadow
            release_threshold=10.0,
        ),
        audit_sink=sink,
    ) as exec_:
        agent = MyAgent(exec_=exec_)
        agent.run("standard happy-path query")

    # Extract pressure samples from audit log
    pressures = [
        e.data["pressure"]
        for e in sink.events if e.kind == "engine.step"
    ]
    assert max(pressures) < 0.5, (
        "Unexpected pressure during happy-path. "
        f"Peak was {max(pressures):.3f}. "
        "If this is intentional, raise the assertion bound."
    )
```

This catches cases where a refactor accidentally increases the
pressure an agent generates without anyone noticing.

## Anti-patterns

**"Just deploy it with defaults."** The defaults in `PressureConfig`
are not tuned for any specific workload. Going straight to enforce
mode with defaults is a good way to block legitimate traffic on
day 1.

**"Skip shadow mode; we'll tune after an incident."** This is
tempting because shadow mode doesn't produce a dramatic launch. It
also pre-loads every incident in the first month of operation onto
your on-call team. Don't.

**"Enforce in shadow, log-only in production."** We've seen this
inverted accidentally, usually because someone set the production
config based on stale documentation. Use the same `PressureConfig`
objects across environments and switch explicitly.

## One worked example

See `examples/shadow_rollout.py` for a runnable example that:

1. Builds a shadow config and runs a synthetic agent.
2. Graduates to log-only with a realistic threshold.
3. Graduates to enforce, and demonstrates the escalation triggering
   correctly.

Running it against your own agent code is a reasonable Phase 0
rehearsal.
