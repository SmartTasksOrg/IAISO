# IAIso Audit Events — Normative Specification

**Version: 1.0**

Audit events are the primary observable output of IAIso. Every state
transition in the pressure engine, every consent check, and every
coordinator action emits a structured event. This spec defines the
stable wire format those events use.

Consumers: SIEMs (Splunk, Datadog, Loki, etc.), observability platforms
that forward logs as metrics, compliance archives, and custom tooling
that replays event streams to reconstruct engine state.

## 1. Envelope

Every event is a JSON object with exactly these top-level fields:

| Field            | Type    | Required | Description                                |
|------------------|---------|----------|--------------------------------------------|
| `schema_version` | string  | ✓        | Version of this spec, e.g. `"1.0"`.        |
| `execution_id`   | string  | ✓        | Execution the event belongs to.            |
| `kind`           | string  | ✓        | Event type. Dotted namespace. See §3.      |
| `timestamp`      | number  | ✓        | Unix seconds with fractional precision.    |
| `data`           | object  | ✓        | Event-specific payload. See §4.            |

- `schema_version` MUST be `"1.0"` for events produced against this spec.
- `execution_id` is the stable identifier of the execution. For
  coordinator-level events, a conventional pseudo-execution ID MAY be
  used (e.g., `"coord:<coordinator_id>"` or `"redis-coord:<id>"`).
- `kind` uses dotted segments: `<component>.<action>`. Components and
  actions follow `[a-z0-9_]+` for portability.
- `timestamp` is Unix time in seconds. Fractional seconds are allowed
  (microsecond precision is typical in the reference implementation).
  Wall-clock source is acceptable; monotonic is not (you can't correlate
  across processes with a monotonic clock).
- `data` is a JSON object. Its keys depend on `kind`. Keys MUST be
  JSON-serializable values.

Implementations MUST emit JSON that validates against
`spec/events/envelope.schema.json`.

## 2. Evolution rules

This is the contract a stable consumer can rely on:

- **Additive changes** (new event kinds, new fields in existing payloads)
  are MINOR bumps (1.0 → 1.1). Existing consumers that ignore unknown
  fields and unknown kinds continue to work.
- **Breaking changes** (removed fields, renamed kinds, changed field
  types, changed payload semantics) require a MAJOR bump (1.x → 2.0).
  When a 2.0 is released, a 1.x → 2.0 migration guide is published and
  the 1.x format continues to be emittable for at least one release.

Consumers MUST handle unknown event kinds without crashing. The safest
default is to log-and-continue; rejecting on unknown kind will break
your pipeline at every MINOR bump.

Consumers MUST handle unknown fields in known payloads without crashing.
Same rationale.

## 3. Event kinds

### 3.1 Core pressure engine

| Kind                    | Triggered when                                              |
|-------------------------|-------------------------------------------------------------|
| `engine.init`           | Engine construction completes.                              |
| `engine.step`           | A step was accounted (before threshold checks).             |
| `engine.escalation`     | Pressure crossed into the escalation zone.                  |
| `engine.release`        | Pressure crossed the release threshold (pre-reset).         |
| `engine.locked`         | Post-release lock engaged.                                  |
| `engine.step.rejected`  | A step was rejected because the engine was locked.          |
| `engine.reset`          | `reset()` was called.                                       |

### 3.2 BoundedExecution wrapper

| Kind                           | Triggered when                                       |
|--------------------------------|------------------------------------------------------|
| `execution.consent_attached`   | A consent scope was attached at execution start.     |
| `execution.closed`             | Execution context manager exited.                    |

### 3.3 Consent checks

| Kind                | Triggered when                                                |
|---------------------|---------------------------------------------------------------|
| `consent.missing`   | Scope required but no consent attached.                       |
| `consent.granted`   | Scope check succeeded.                                        |
| `consent.denied`    | Scope check failed because token did not grant the scope.     |

### 3.4 Coordinator

| Kind                                 | Triggered when                                |
|--------------------------------------|-----------------------------------------------|
| `coordinator.init`                   | Coordinator constructed.                      |
| `coordinator.execution_registered`   | An execution joined.                          |
| `coordinator.execution_unregistered` | An execution left.                            |
| `coordinator.escalation`             | Aggregate pressure entered the escalation zone. |
| `coordinator.release`                | Aggregate pressure crossed the release threshold. |
| `coordinator.returned_to_nominal`    | Aggregate pressure fell below escalation.     |
| `coordinator.reset`                  | Operator reset the coordinator.               |
| `coordinator.callback_error`         | A user callback threw.                        |

## 4. Payloads

This section defines what MUST appear in `data` for each event kind.
Implementations MAY include additional fields beyond what is listed;
they MUST NOT omit required fields.

### engine.init
```
{ "pressure": 0.0 }
```

### engine.step
```
{
  "step": integer,          // 1-indexed step counter, post-increment
  "pressure": number,       // Post-step pressure in [0, 1]
  "delta": number,          // Gross pressure added this step (before decay)
  "decay": number,          // Gross pressure removed this step
  "tokens": integer,        // As supplied
  "tool_calls": integer,    // As supplied
  "depth": integer,         // As supplied
  "tag": string | null      // As supplied
}
```

Note: `delta` and `decay` are GROSS, not net. Net = `delta - decay`. The
reference implementation also retains `delta - decay` in
`engine.last_delta` but that value is not part of the event payload.

### engine.escalation
```
{
  "pressure": number,       // Pressure that triggered the escalation
  "threshold": number       // Configured escalation_threshold
}
```

### engine.release
```
{
  "pressure": number,       // Pressure before reset
  "threshold": number       // Configured release_threshold
}
```

### engine.locked
```
{ "reason": "post_release_lock" }   // Only reason value used in v1.0
```

### engine.step.rejected
```
{
  "reason": "locked",       // Only reason value used in v1.0
  "requested_tokens": integer,
  "requested_tools": integer
}
```

### engine.reset
```
{ "pressure": 0.0 }
```

### execution.consent_attached
```
{
  "subject": string,        // scope.subject
  "scopes": [string],       // scope.scopes
  "jti": string             // scope.jti
}
```

### execution.closed
```
{
  "final_pressure": number,
  "final_lifecycle": string,   // one of "init"/"running"/"escalated"/"locked"
  "exception": string | null   // exception type name or null
}
```

### consent.missing
```
{ "requested": string }
```

### consent.granted
```
{
  "requested": string,      // the requested scope
  "jti": string             // token's jti claim
}
```

### consent.denied
```
{
  "requested": string,
  "granted": [string],      // what the token actually granted
  "jti": string
}
```

### coordinator.init
```
{
  "coordinator_id": string,
  "aggregator": string,     // "sum" | "mean" | "max" | "weighted_sum"
  "backend": string         // "memory" | "redis"
  // implementations MAY add backend-specific fields
}
```

### coordinator.execution_registered / coordinator.execution_unregistered
```
{ "execution_id": string }
```

### coordinator.escalation / coordinator.release
```
{
  "aggregate_pressure": number,
  "threshold": number
}
```

### coordinator.returned_to_nominal
```
{ "aggregate_pressure": number }
```

### coordinator.reset
```
{ "fleet_size": integer }  // Number of executions whose pressure was zeroed
```

### coordinator.callback_error
```
{
  "callback": string,       // "on_escalation" | "on_release"
  "error": string           // exception message
}
```

## 5. Equality for conformance vectors

When a conformance vector compares events, the following fields are
compared:

- `schema_version`
- `execution_id`
- `kind`
- Every key listed in the per-kind payload specification above.

These fields are NOT compared (they are environmental):

- `timestamp` — cannot be deterministic across implementations without
  scripting all calls to the wall clock, which is onerous.
- Payload fields NOT listed in §4 — implementations may add their own.

A conformant implementation passes an event vector if, for every
specified event in order, it emits an event with:

- Identical `schema_version`, `execution_id`, `kind`.
- All specified payload fields present with identical values (within
  `1e-9` tolerance for numbers).
- In the correct position in the event stream (relative ordering).

## 6. Test vectors

`spec/events/vectors.json` pairs engine inputs with expected event
streams. Each vector:

```json
{
  "name": "one_step_emits_init_then_step",
  "config": {...},
  "clock": [0.0, 0.1],
  "steps": [{"tokens": 100, "tool_calls": 0, "depth": 0, "tag": null}],
  "expected_events": [
    {"kind": "engine.init", "data": {"pressure": 0.0}},
    {"kind": "engine.step", "data": {"step": 1, "pressure": 0.0, "delta": 0.0015, "decay": 0.02, "tokens": 100, "tool_calls": 0, "depth": 0, "tag": null}}
  ]
}
```

The runner constructs a pressure engine, feeds it inputs, captures
emitted events, and compares against the expected stream using §5
equality.

## 7. Sink delivery

Sink-specific wire formats (Splunk HEC, Datadog Logs intake, Loki push
API, etc.) are adapters that transform the envelope in §1 into the
format each vendor expects. They are out of scope for this spec.

If you are writing a new sink in a new language, the envelope in §1 is
the input; the vendor's documentation is the output.
