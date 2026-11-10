"""Tests for retry_after and CircuitBreaker."""

from __future__ import annotations

import pytest

from iaiso import PressureConfig
from iaiso.core.engine import PressureEngine
from iaiso.reliability import (
    CircuitBreaker,
    CircuitBreakerOpen,
    retry_after_seconds,
)


# -- retry_after_seconds ----------------------------------------------------


def test_retry_after_already_below_target_returns_minimum() -> None:
    eng = PressureEngine(
        PressureConfig(
            escalation_threshold=0.8,
            release_threshold=0.95,
            dissipation_per_second=0.1,
        ),
        execution_id="x",
    )
    # pressure is 0, well below target — should return minimum
    assert retry_after_seconds(eng, minimum_seconds=2.0) == 2.0


def test_retry_after_with_dissipation() -> None:
    cfg = PressureConfig(
        escalation_threshold=0.8,
        release_threshold=0.95,
        dissipation_per_second=0.1,
        dissipation_per_step=0.0,
        token_coefficient=1.0,
    )
    eng = PressureEngine(cfg, execution_id="x")
    # Force pressure to ~0.9
    eng._pressure = 0.9  # type: ignore[attr-defined]
    # Target default = 0.8 - 0.1 = 0.7. Excess = 0.2. Rate = 0.1/s.
    # Expected: ~2s.
    s = retry_after_seconds(eng)
    assert 1.9 <= s <= 2.1


def test_retry_after_no_passive_dissipation_returns_max() -> None:
    cfg = PressureConfig(
        dissipation_per_step=0.0,
        dissipation_per_second=0.0,
    )
    eng = PressureEngine(cfg, execution_id="x")
    eng._pressure = 0.9  # type: ignore[attr-defined]
    # No way to passively recover — should clamp to maximum.
    assert retry_after_seconds(eng, maximum_seconds=60.0) == 60.0


def test_retry_after_respects_maximum() -> None:
    cfg = PressureConfig(
        dissipation_per_second=0.0001,  # very slow dissipation
        dissipation_per_step=0.0,
    )
    eng = PressureEngine(cfg, execution_id="x")
    eng._pressure = 0.99  # type: ignore[attr-defined]
    # Would take thousands of seconds at that rate, but clamp to max.
    assert retry_after_seconds(eng, maximum_seconds=120.0) == 120.0


# -- CircuitBreaker ---------------------------------------------------------


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def advance(self, secs: float) -> None:
        self.t += secs


def test_breaker_starts_closed() -> None:
    cb = CircuitBreaker()
    assert cb.state == "closed"


def test_breaker_opens_after_threshold_failures() -> None:
    clock = FakeClock()
    cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=30.0,
                        clock=clock)

    def boom() -> None:
        raise RuntimeError("nope")

    for _ in range(3):
        with pytest.raises(RuntimeError):
            cb.call(boom)

    assert cb.state == "open"


def test_open_breaker_rejects_calls() -> None:
    clock = FakeClock()
    cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=30.0,
                        clock=clock)

    with pytest.raises(RuntimeError):
        cb.call(lambda: (_ for _ in ()).throw(RuntimeError("x")))

    with pytest.raises(CircuitBreakerOpen):
        cb.call(lambda: "ok")


def test_breaker_transitions_to_half_open_after_cooldown() -> None:
    clock = FakeClock()
    cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=10.0,
                        clock=clock)
    with pytest.raises(RuntimeError):
        cb.call(lambda: (_ for _ in ()).throw(RuntimeError("x")))
    assert cb.state == "open"

    clock.advance(5.0)
    assert cb.state == "open"

    clock.advance(5.1)
    assert cb.state == "half_open"


def test_half_open_probe_success_closes_breaker() -> None:
    clock = FakeClock()
    cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=1.0,
                        clock=clock)
    with pytest.raises(RuntimeError):
        cb.call(lambda: (_ for _ in ()).throw(RuntimeError("x")))
    clock.advance(1.1)

    result = cb.call(lambda: "ok")
    assert result == "ok"
    assert cb.state == "closed"


def test_half_open_probe_failure_reopens_breaker() -> None:
    clock = FakeClock()
    cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=1.0,
                        clock=clock)
    with pytest.raises(RuntimeError):
        cb.call(lambda: (_ for _ in ()).throw(RuntimeError("first")))
    clock.advance(1.1)

    # In half_open, probe fails
    with pytest.raises(RuntimeError):
        cb.call(lambda: (_ for _ in ()).throw(RuntimeError("second")))

    assert cb.state == "open"
    # Should require a fresh full cooldown
    clock.advance(0.5)
    with pytest.raises(CircuitBreakerOpen):
        cb.call(lambda: "ok")


def test_reset_forces_closed() -> None:
    clock = FakeClock()
    cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=100.0,
                        clock=clock)
    with pytest.raises(RuntimeError):
        cb.call(lambda: (_ for _ in ()).throw(RuntimeError("x")))
    assert cb.state == "open"
    cb.reset()
    assert cb.state == "closed"


def test_breaker_ignores_non_failure_exceptions() -> None:
    cb = CircuitBreaker(
        failure_threshold=1,
        failure_exceptions=(ValueError,),
    )
    # KeyError is not in failure_exceptions — should pass through without
    # tripping the breaker.
    with pytest.raises(KeyError):
        cb.call(lambda: (_ for _ in ()).throw(KeyError("x")))
    assert cb.state == "closed"


def test_steady_state_success_resets_failure_count() -> None:
    clock = FakeClock()
    cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=10.0,
                        clock=clock)
    # Two failures...
    for _ in range(2):
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("x")))
    # ...then a success should clear the count
    cb.call(lambda: "ok")
    snap = cb.snapshot()
    assert snap.failures == 0
    # Now two more failures shouldn't trip it (need 3 consecutive)
    for _ in range(2):
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("x")))
    assert cb.state == "closed"
