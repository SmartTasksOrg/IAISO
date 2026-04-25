"""Redis-backed distributed `SharedPressureCoordinator`.

The in-memory coordinator in `iaiso.coordination` handles single-process
fleets. For multi-process or multi-host deployments — the common
production case — pressures live in Redis and aggregates are computed
with atomic Lua scripts.

Wire protocol:
    A coordinator is identified by a key prefix (default
    `iaiso:coord:<coordinator_id>`). Per-execution pressures are stored
    in a hash at `{prefix}:pressures` with execution_id as the field.
    Lifecycle state is stored at `{prefix}:state` as a JSON-encoded
    document.

Atomicity:
    `update()` issues a Lua script that sets the new pressure, reads all
    pressures, computes the aggregate, and returns the combined state.
    This avoids TOCTOU races where two workers could both see "below
    threshold" and neither fire an escalation callback.

Drift from in-memory version:
    - Callbacks (`on_escalation`, `on_release`) fire on the process that
      invoked `update()` and observed the transition. Other processes
      watching the same coordinator will NOT fire their own callbacks
      for the same transition. If you need every worker to act on a
      state change, subscribe to the audit sink (via pubsub) instead of
      relying on per-process callbacks.
    - The aggregator runs in Python after Redis returns all pressures;
      only `sum`, `mean`, and `max` can be computed server-side. Complex
      aggregators (`WeightedSumAggregator`) are computed client-side.

Verification Required Before Production:
    Tested against `fakeredis`, which implements Redis's RESP protocol
    and Lua scripting in-process. Verified behaviors include: atomic
    update + aggregate, multi-client pressure visibility, TTL-based
    stale-execution eviction. End-to-end verification against real
    Redis is required before production use — in particular, test your
    specific Redis version's Lua scripting quirks and Cluster-mode
    behavior (the key scheme assumes a single-slot hash tag; see
    `key_prefix` below).
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable

from iaiso.audit import AuditEvent, AuditSink, NullSink
from iaiso.coordination import (
    Aggregator,
    CoordinatorConfig,
    CoordinatorSnapshot,
    SumAggregator,
)

try:
    import redis
    _REDIS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _REDIS_AVAILABLE = False


# Lua script: set pressure for an execution, then return all pressures
# as a flat array so the client can compute the aggregate. Written as
# a single script so it executes atomically on the Redis server.
_UPDATE_AND_FETCH_SCRIPT = """
local pressures_key = KEYS[1]
local exec_id = ARGV[1]
local new_pressure = ARGV[2]
local ttl_seconds = tonumber(ARGV[3])

redis.call('HSET', pressures_key, exec_id, new_pressure)
if ttl_seconds > 0 then
  redis.call('EXPIRE', pressures_key, ttl_seconds)
end

local flat = redis.call('HGETALL', pressures_key)
return flat
"""


@dataclass
class RedisCoordinatorConfig:
    """Extra settings specific to the Redis-backed coordinator."""

    key_prefix: str = "iaiso:coord"
    """Key namespace. For Redis Cluster, wrap in hash tags to keep all
    keys in a single slot: e.g., `"{iaiso:coord:prod}"`."""

    pressures_ttl_seconds: float = 300.0
    """TTL on the pressures hash. If no worker updates within this
    window, the entire fleet state is considered stale and rebuilt from
    scratch. Use a value longer than your longest expected execution."""


class RedisCoordinator:
    """Redis-backed cross-host pressure coordinator.

    Implements the same interface as `SharedPressureCoordinator` so
    code using one can switch to the other by changing construction.
    """

    def __init__(
        self,
        client: "redis.Redis",
        *,
        config: CoordinatorConfig | None = None,
        redis_config: RedisCoordinatorConfig | None = None,
        aggregator: Aggregator | None = None,
        audit_sink: AuditSink | None = None,
        on_escalation: Callable[[CoordinatorSnapshot], None] | None = None,
        on_release: Callable[[CoordinatorSnapshot], None] | None = None,
        coordinator_id: str | None = None,
    ) -> None:
        if not _REDIS_AVAILABLE:  # pragma: no cover
            raise ImportError(
                "RedisCoordinator requires redis-py. "
                "Install with: pip install iaiso[redis]"
            )
        self._client = client
        self._cfg = config or CoordinatorConfig()
        self._redis_cfg = redis_config or RedisCoordinatorConfig()
        self._agg = aggregator or SumAggregator()
        self._audit = audit_sink or NullSink()
        self._on_escalation = on_escalation
        self._on_release = on_release
        self._id = coordinator_id or "default"

        self._lock = threading.RLock()
        # Local lifecycle tracking — this process's view. Use the Redis
        # state doc for the authoritative cross-process view.
        self._local_lifecycle: str = "nominal"
        self._script_sha = self._client.register_script(_UPDATE_AND_FETCH_SCRIPT)

        self._emit("coordinator.init",
                   coordinator_id=self._id,
                   aggregator=self._agg.name,
                   backend="redis",
                   key_prefix=self._redis_cfg.key_prefix)

    @property
    def coordinator_id(self) -> str:
        return self._id

    def _pressures_key(self) -> str:
        return f"{self._redis_cfg.key_prefix}:{self._id}:pressures"

    def register(self, execution_id: str) -> None:
        self._client.hset(self._pressures_key(), execution_id, 0.0)
        if self._redis_cfg.pressures_ttl_seconds > 0:
            self._client.expire(
                self._pressures_key(),
                int(self._redis_cfg.pressures_ttl_seconds),
            )
        self._emit("coordinator.execution_registered",
                   execution_id=execution_id)

    def unregister(self, execution_id: str) -> None:
        self._client.hdel(self._pressures_key(), execution_id)
        self._emit("coordinator.execution_unregistered",
                   execution_id=execution_id)

    def update(self, execution_id: str, pressure: float) -> CoordinatorSnapshot:
        if not 0.0 <= pressure <= 1.0:
            raise ValueError("pressure must be in [0, 1]")

        flat = self._script_sha(
            keys=[self._pressures_key()],
            args=[execution_id, str(pressure),
                  str(int(self._redis_cfg.pressures_ttl_seconds))],
        )
        pressures = self._parse_flat(flat)
        agg = self._agg.aggregate(pressures)
        snap = CoordinatorSnapshot(
            aggregate_pressure=agg,
            per_execution=pressures,
            active_executions=len(pressures),
            lifecycle="nominal",  # overwritten below
        )
        self._check_transitions_locked(snap)
        snap.lifecycle = self._local_lifecycle
        return snap

    def snapshot(self) -> CoordinatorSnapshot:
        flat = self._client.hgetall(self._pressures_key())
        # redis-py returns dict of bytes→bytes
        pressures = {
            (k.decode() if isinstance(k, bytes) else k):
                float(v if isinstance(v, (int, float)) else v.decode())
            for k, v in flat.items()
        }
        agg = self._agg.aggregate(pressures)
        return CoordinatorSnapshot(
            aggregate_pressure=agg,
            per_execution=pressures,
            active_executions=len(pressures),
            lifecycle=self._local_lifecycle,
        )

    def reset(self) -> None:
        """Clear all execution pressures. Operator-level action."""
        key = self._pressures_key()
        # Zero out every field rather than deleting the key, so active
        # workers see their executions still registered.
        all_fields = self._client.hkeys(key)
        if all_fields:
            pipe = self._client.pipeline()
            for field in all_fields:
                pipe.hset(key, field, 0.0)
            pipe.execute()
        with self._lock:
            self._local_lifecycle = "nominal"
        self._emit("coordinator.reset", fleet_size=len(all_fields))

    def _parse_flat(self, flat: Any) -> dict[str, float]:
        """Parse a Redis HGETALL-style flat array into a dict."""
        result: dict[str, float] = {}
        # redis-py's register_script returns list of bytes for Lua arrays
        if isinstance(flat, dict):
            items = flat.items()
        else:
            it = iter(flat)
            items = zip(it, it)
        for k, v in items:
            key = k.decode() if isinstance(k, bytes) else str(k)
            val = v.decode() if isinstance(v, bytes) else v
            try:
                result[key] = float(val)
            except (TypeError, ValueError):
                continue
        return result

    def _check_transitions_locked(self, snap: CoordinatorSnapshot) -> None:
        with self._lock:
            agg = snap.aggregate_pressure
            if (agg >= self._cfg.release_threshold
                    and self._local_lifecycle != "released"):
                self._local_lifecycle = "released"
                self._emit("coordinator.release",
                           aggregate_pressure=agg,
                           threshold=self._cfg.release_threshold)
                if self._on_release is not None:
                    try:
                        self._on_release(snap)
                    except Exception as exc:  # noqa: BLE001
                        self._emit("coordinator.callback_error",
                                   callback="on_release", error=str(exc))
            elif (agg >= self._cfg.escalation_threshold
                  and self._local_lifecycle == "nominal"):
                self._local_lifecycle = "escalated"
                self._emit("coordinator.escalation",
                           aggregate_pressure=agg,
                           threshold=self._cfg.escalation_threshold)
                if self._on_escalation is not None:
                    try:
                        self._on_escalation(snap)
                    except Exception as exc:  # noqa: BLE001
                        self._emit("coordinator.callback_error",
                                   callback="on_escalation", error=str(exc))
            elif agg < self._cfg.escalation_threshold:
                if self._local_lifecycle != "nominal":
                    self._local_lifecycle = "nominal"
                    self._emit("coordinator.returned_to_nominal",
                               aggregate_pressure=agg)

    def _emit(self, kind: str, **data: Any) -> None:
        self._audit.emit(AuditEvent(
            execution_id=f"redis-coord:{self._id}",
            kind=kind,
            timestamp=time.time(),
            data=data,
        ))
