# Cross-Execution Coordination

When multiple agents share a resource — an API quota, a database, a
downstream rate-limited service — you want fleet-wide visibility into
total pressure, not just per-agent pressure. An agent at 0.3 pressure
isn't concerning; 100 agents each at 0.3 might be.

`SharedPressureCoordinator` is the component that gives you that view.

## Usage

```python
from iaiso import (
    BoundedExecution,
    PressureConfig,
    SharedPressureCoordinator,
    SumAggregator,
    CoordinatorConfig,
)

coordinator = SharedPressureCoordinator(
    config=CoordinatorConfig(
        escalation_threshold=3.0,   # aggregate units; depends on aggregator
        release_threshold=5.0,
    ),
    aggregator=SumAggregator(),
    on_escalation=lambda snap: alert(
        f"Fleet pressure {snap.aggregate_pressure:.2f} "
        f"across {snap.active_executions} agents"
    ),
)

# Per-agent code:
def run_agent(task, exec_id):
    coordinator.register(exec_id)
    try:
        with BoundedExecution.start(execution_id=exec_id) as exec_:
            for step in task.steps():
                outcome = exec_.record_step(
                    tokens=step.tokens,
                    tool_calls=step.tool_calls,
                )
                # Report up to the coordinator every step
                coordinator.update(exec_id, exec_.snapshot().pressure)
    finally:
        coordinator.unregister(exec_id)
```

## Choosing an aggregator

The coordinator supports four aggregation policies. Pick based on what
"fleet is hot" actually means for your system:

| Aggregator              | Aggregate value                                  | Use when                                           |
|-------------------------|--------------------------------------------------|----------------------------------------------------|
| `SumAggregator`         | Σ individual pressures                           | Shared additive resource (combined API quota)      |
| `MeanAggregator`        | (Σ individual pressures) / n                     | You care about average load, bounded in [0, 1]     |
| `MaxAggregator`         | max(individual pressures)                        | Any single runaway is concerning (strict mode)     |
| `WeightedSumAggregator` | Σ (weight[eid] × pressure[eid])                  | Some agents cost more than others                  |

The thresholds are in the same units as the aggregator's output. For
`SumAggregator` with a fleet of 20 agents, an escalation threshold of
3.0 means "fire when the total pressure reaches 3.0 summed across all
20 agents" — which averages to 0.15/agent. Calibrate accordingly.

## Thresholds

`CoordinatorConfig` has its own escalation and release thresholds,
independent of any individual engine's thresholds. A fleet can escalate
even when every individual agent is below its own threshold — that's
the whole point.

The coordinator calls `on_escalation` and `on_release` callbacks when
thresholds are crossed. `on_escalation` may be called repeatedly if
pressure stays above the threshold; `notify_cooldown_seconds` rate-limits
those repeated calls. `on_release` is called exactly once per release
event.

## Multi-process deployments

The in-memory `SharedPressureCoordinator` is scoped to a single process.
For fleets spread across processes or hosts, use
`iaiso.coordination.redis.RedisCoordinator`, which implements the same
interface against a Redis-backed keyspace with atomic Lua updates. See
[`../spec/coordinator/README.md`](../spec/coordinator/README.md) for
the normative wire format and keyspace specification. Operators who
prefer etcd or a custom shared store can build against the same
six-method interface; the draft gRPC wire format in
[`../spec/coordinator/wire.proto`](../spec/coordinator/wire.proto)
describes the direction for a future native sidecar.
