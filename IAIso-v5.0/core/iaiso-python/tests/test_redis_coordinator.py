"""Tests for Redis-backed coordinator."""

from __future__ import annotations

import fakeredis
import pytest

from iaiso import MemorySink
from iaiso.coordination import (
    CoordinatorConfig,
    MaxAggregator,
    SumAggregator,
)
from iaiso.coordination.redis import RedisCoordinator, RedisCoordinatorConfig


@pytest.fixture
def redis_client() -> fakeredis.FakeRedis:
    # fakeredis supports Lua scripting which is what we need
    return fakeredis.FakeRedis()


def test_single_client_update(redis_client: fakeredis.FakeRedis) -> None:
    coord = RedisCoordinator(
        redis_client,
        config=CoordinatorConfig(escalation_threshold=1.0,
                                 release_threshold=2.0),
        aggregator=SumAggregator(),
        coordinator_id="test-1",
    )
    coord.register("a")
    snap = coord.update("a", 0.3)
    assert snap.aggregate_pressure == pytest.approx(0.3)
    assert snap.active_executions == 1


def test_two_clients_see_shared_state(redis_client: fakeredis.FakeRedis) -> None:
    """The whole point of Redis-backed: two processes (here, two client
    instances) see the same aggregate."""
    coord_a = RedisCoordinator(
        redis_client,
        config=CoordinatorConfig(escalation_threshold=1.0,
                                 release_threshold=2.0),
        coordinator_id="shared",
    )
    coord_b = RedisCoordinator(
        redis_client,
        config=CoordinatorConfig(escalation_threshold=1.0,
                                 release_threshold=2.0),
        coordinator_id="shared",
    )
    coord_a.register("worker-1")
    coord_b.register("worker-2")

    coord_a.update("worker-1", 0.4)
    snap = coord_b.update("worker-2", 0.5)
    # coord_b sees both workers' pressures
    assert snap.aggregate_pressure == pytest.approx(0.9)
    assert snap.active_executions == 2


def test_escalation_callback_fires_locally(
    redis_client: fakeredis.FakeRedis,
) -> None:
    calls: list[float] = []
    coord = RedisCoordinator(
        redis_client,
        config=CoordinatorConfig(escalation_threshold=1.0,
                                 release_threshold=2.0),
        on_escalation=lambda snap: calls.append(snap.aggregate_pressure),
        coordinator_id="esc",
    )
    coord.register("a")
    coord.register("b")
    coord.update("a", 0.5)
    # Second update pushes aggregate over the escalation threshold
    coord.update("b", 0.6)
    assert len(calls) == 1


def test_multi_client_only_local_callback_fires(
    redis_client: fakeredis.FakeRedis,
) -> None:
    """Cross-process callback semantics: each process fires callbacks
    for transitions it observed, not for transitions driven by others."""
    a_calls: list[float] = []
    b_calls: list[float] = []
    coord_a = RedisCoordinator(
        redis_client,
        config=CoordinatorConfig(escalation_threshold=1.0,
                                 release_threshold=2.0),
        on_escalation=lambda snap: a_calls.append(snap.aggregate_pressure),
        coordinator_id="x",
    )
    coord_b = RedisCoordinator(
        redis_client,
        config=CoordinatorConfig(escalation_threshold=1.0,
                                 release_threshold=2.0),
        on_escalation=lambda snap: b_calls.append(snap.aggregate_pressure),
        coordinator_id="x",
    )
    coord_a.register("w1")
    coord_b.register("w2")
    coord_a.update("w1", 0.6)
    coord_a.update("w1", 0.9)  # aggregate now 0.9 + 0 = 0.9 (no w2 yet)
    # w2 still at 0, so no escalation. Now register and drive w2 up
    coord_b.update("w2", 0.5)  # aggregate 0.9 + 0.5 = 1.4, escalation fires on B
    assert len(b_calls) == 1
    # A still nominal in its local view until it sees the high aggregate
    coord_a.update("w1", 0.9)  # observes the full aggregate now
    assert len(a_calls) == 1


def test_reset_clears_pressures(redis_client: fakeredis.FakeRedis) -> None:
    coord = RedisCoordinator(
        redis_client,
        coordinator_id="rst",
    )
    coord.register("a")
    coord.register("b")
    coord.update("a", 0.5)
    coord.update("b", 0.5)
    assert coord.snapshot().aggregate_pressure == pytest.approx(1.0)
    coord.reset()
    assert coord.snapshot().aggregate_pressure == pytest.approx(0.0)


def test_unregister_removes_from_aggregate(
    redis_client: fakeredis.FakeRedis,
) -> None:
    coord = RedisCoordinator(
        redis_client,
        aggregator=MaxAggregator(),
        coordinator_id="unreg",
    )
    coord.register("a")
    coord.register("b")
    coord.update("a", 0.9)
    coord.update("b", 0.1)
    assert coord.snapshot().aggregate_pressure == pytest.approx(0.9)
    coord.unregister("a")
    assert coord.snapshot().aggregate_pressure == pytest.approx(0.1)


def test_audit_events_emitted(redis_client: fakeredis.FakeRedis) -> None:
    sink = MemorySink()
    coord = RedisCoordinator(
        redis_client,
        config=CoordinatorConfig(escalation_threshold=0.5,
                                 release_threshold=1.5),
        audit_sink=sink,
        coordinator_id="audit",
    )
    coord.register("a")
    coord.update("a", 0.6)  # triggers escalation
    kinds = [e.kind for e in sink.events]
    assert "coordinator.init" in kinds
    assert "coordinator.execution_registered" in kinds
    assert "coordinator.escalation" in kinds


def test_invalid_pressure_rejected(redis_client: fakeredis.FakeRedis) -> None:
    coord = RedisCoordinator(redis_client, coordinator_id="bad")
    with pytest.raises(ValueError):
        coord.update("a", 1.5)


def test_namespace_isolation(redis_client: fakeredis.FakeRedis) -> None:
    """Two coordinators with different IDs must not see each other's state."""
    a = RedisCoordinator(redis_client, coordinator_id="tenant-a")
    b = RedisCoordinator(redis_client, coordinator_id="tenant-b")
    a.register("x")
    a.update("x", 0.8)
    # b sees nothing
    assert b.snapshot().active_executions == 0
    assert b.snapshot().aggregate_pressure == 0.0
