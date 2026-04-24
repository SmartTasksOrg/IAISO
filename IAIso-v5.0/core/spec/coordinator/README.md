# IAIso Coordinator — Normative Specification

**Version: 1.0** for Redis backend; gRPC wire format is **DRAFT**
(subject to change before first cross-language port).

A coordinator is fleet-wide shared state: it tracks pressures from
multiple IAIso executions — potentially on different processes, hosts,
or even languages — and combines them into a single aggregate pressure
that all participants can react to.

IAIso ships two coordinator backends in the Python reference:

1. **In-memory** (`iaiso.coordination.SharedPressureCoordinator`) — for
   single-process fleets (a few worker threads in one service).
   Single-language; not cross-port.
2. **Redis** (`iaiso.coordination.redis.RedisCoordinator`) — for
   multi-process, multi-host, multi-language fleets. **This is the
   only backend that is normative for cross-language interop**, because
   the wire format (Redis keys, hash layout, Lua scripts) is the contract.

A future third backend will be a native gRPC coordinator sidecar; the
draft proto is in `wire.proto`. Until that sidecar is shipped and its
semantics are frozen, implementations SHOULD target the Redis backend
for cross-language deployments.

## 1. Redis keyspace

A coordinator is identified by a tuple `(key_prefix, coordinator_id)`.
The default `key_prefix` is `iaiso:coord`; the default `coordinator_id`
is `"default"`. Together they yield keys under a single namespace:

| Key                                          | Redis type  | Contents                                  |
|----------------------------------------------|-------------|-------------------------------------------|
| `{prefix}:{id}:pressures`                    | hash        | field = execution_id, value = pressure    |

Field values are floats serialized as strings (per standard Redis
conventions). Keys that are not in the `pressures` hash belong to
future IAIso versions or out-of-band tooling — implementations MUST NOT
rely on their absence.

### 1.1 Redis Cluster compatibility

In Redis Cluster, a single atomic operation (Lua script) MUST have all
its keys in the same hash slot. Coordinators use a single key, so no
slot-routing is required for §1.2 below. However if an operator
deploys multiple coordinator IDs inside Cluster and wants them
co-located, they SHOULD wrap the prefix in hash tags:

```
key_prefix = "{iaiso:coord:prod}"
```

This keeps all of a production fleet's coordinator keys in one slot.

### 1.2 The atomic update script

The write path is a single Lua script executed server-side:

```lua
-- KEYS[1]: the pressures hash key
-- ARGV[1]: execution_id
-- ARGV[2]: new pressure as a string
-- ARGV[3]: TTL in integer seconds; 0 to skip

local pressures_key = KEYS[1]
local exec_id       = ARGV[1]
local new_pressure  = ARGV[2]
local ttl_seconds   = tonumber(ARGV[3])

redis.call('HSET', pressures_key, exec_id, new_pressure)
if ttl_seconds > 0 then
  redis.call('EXPIRE', pressures_key, ttl_seconds)
end

return redis.call('HGETALL', pressures_key)
```

The return value is an HGETALL flat array: `[field1, value1, field2,
value2, ...]`. The client reassembles pairs and feeds them to the
aggregator.

**Atomicity.** This is one `EVAL` call, so no other client can observe
the hash between the HSET and the HGETALL. Two workers both pushing
pressure up past the escalation threshold will each receive the
post-HSET snapshot, and each independently crosses the threshold at
most once (per-client) against the snapshot it observed.

**Stale-state eviction.** The EXPIRE refreshes on every write. If every
execution worker dies at once, after `ttl_seconds` the key vanishes and
the next worker starts from a clean slate. A zero TTL means the hash
never expires; set explicitly if you want behavior that persists
across restarts.

### 1.3 Script registration

The reference implementation calls `SCRIPT LOAD` once at coordinator
init (via `redis-py`'s `register_script`) and thereafter invokes
`EVALSHA` with the returned digest. Ports MAY use the same mechanism
or may inline `EVAL` calls on each write. Both produce identical
semantics. `EVALSHA` is strictly a performance optimization.

### 1.4 Reset operation

`reset()` on a coordinator is not a Lua script; it is a pipelined
sequence of `HSET field 0.0` commands across every field returned by
`HKEYS`. This deliberately does NOT delete the hash, so active workers
still see their execution IDs registered and can continue pushing
updates.

Conformant implementations MAY optimize this with a Lua script, but
the observable result MUST be: every field in the hash set to `"0.0"`,
no fields removed, TTL unchanged.

### 1.5 Cross-language interop contract

Any IAIso-conformant coordinator client, regardless of language, that
connects to the same Redis instance with the same `(key_prefix,
coordinator_id)` tuple MUST:

- Read pressures from `{prefix}:{id}:pressures` as an HGETALL hash.
- Write pressures via the Lua script above, passing the same KEYS/ARGV
  positions.
- Serialize float values as decimal strings accepted by the platform's
  `float()` / `strconv.ParseFloat` / `Double.parseDouble`, etc.

This gives a Node-language execution on host A and a Python execution
on host B identical views of fleet pressure in real time, without either
knowing the other's language.

## 2. Emitted events

Coordinator events use `execution_id` of the form
`"redis-coord:<coordinator_id>"` or `"coord:<coordinator_id>"` per
backend. Fields are specified in `spec/events/README.md §3.4` and
`spec/events/payloads.schema.json`.

## 3. Aggregators

Three aggregators are fully server-computable when needed (though the
Python reference keeps them client-side for simplicity):

- `sum` → `SUM(values)`
- `mean` → `SUM(values) / COUNT(values)` (if count ≥ 1)
- `max` → `MAX(values)`

`weighted_sum` is NOT server-computable without pushing per-execution
weights into Redis. The reference computes it client-side. Any
implementation may do the same; no Redis-level contract applies.

## 4. Draft gRPC wire format (pre-1.0, subject to change)

See `wire.proto` in this directory for the in-progress protobuf
definition for a future native coordinator sidecar. This is labeled
DRAFT. It is NOT part of the conformance contract for IAIso 1.0.

It is published here to:

1. Pin down the intended shape so the v1.0 Redis-backed port doesn't
   accidentally lock in a different vocabulary.
2. Allow early implementations to prototype against it.
3. Invite RFC-style feedback before the gRPC backend becomes normative.

Treat the proto as a design sketch. Do not ship production code that
depends on the wire format being stable across IAIso releases until
the DRAFT marker is removed (expected: IAIso spec 1.1 or 2.0).

## 5. Conformance

There are no normative test vectors for the coordinator in IAIso 1.0.
Coordinator conformance is defined by:

- Correct interaction with the Redis keyspace per §1.
- Correct emitted events per `spec/events/`.
- Correct aggregator math (the aggregators are pure functions; any
  implementation that computes `SUM`, `MEAN`, `MAX` correctly is fine).

Test vectors will be added when the gRPC wire format is un-drafted.

## 6. Non-goals

The coordinator does NOT provide:

- **Strong consistency across partitions.** Redis's default replication
  is async. A split between the writer and a reader can produce brief
  inconsistency. For correctness-critical systems, use synchronous
  replication (`WAIT`) or a consensus store — but the extra latency
  typically dominates.
- **Ordering guarantees on aggregate updates.** A worker that writes
  `p = 0.9` right after `p = 0.1` may observe either value as the
  "last seen" on a racy reader. The aggregator sees the post-write
  snapshot, which is correct; reader-observers of the snapshot across
  multiple reads may see values out of any particular worker's order.
- **Exactly-once semantics for callbacks.** `on_escalation` / `on_release`
  fire on the process that observed the transition. See the Python
  reference's `drift from in-memory version` note. If every worker
  needs to react, subscribe to the event stream (pub/sub); don't rely
  on per-process callbacks for fan-out.
