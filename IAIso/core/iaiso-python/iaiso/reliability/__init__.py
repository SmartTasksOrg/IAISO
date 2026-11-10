"""Reliability primitives for IAIso agents.

Two patterns that most production agent deployments need:

1. **Retry-after hints.** When pressure escalates, the caller needs to
   know when it's worth trying again. `retry_after_seconds()` computes
   this from the current pressure, thresholds, and dissipation rate.

2. **Circuit breakers.** When a downstream tool / API / model repeatedly
   fails, a circuit breaker trips and short-circuits further calls for
   a cooldown period. This prevents agents from producing thousands of
   failed calls during an outage — and, combined with IAIso's pressure
   engine, ensures those calls don't accumulate pressure.

Both are intentionally small, dependency-free, and thread-safe.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

from iaiso.core.engine import PressureConfig, PressureEngine


def retry_after_seconds(
    engine: PressureEngine,
    *,
    target_pressure: float | None = None,
    minimum_seconds: float = 1.0,
    maximum_seconds: float = 300.0,
) -> float:
    """Estimate how long until pressure drops to a retry-safe level.

    Uses the engine's configured dissipation rate to compute the
    wall-clock interval required. Clamps to a configurable range so
    callers get a reasonable hint even under edge cases (zero
    dissipation, already-below-target, etc.).

    Args:
        engine: The pressure engine to compute for.
        target_pressure: The pressure level at which retry is safe.
            Defaults to `escalation_threshold - 0.1`.
        minimum_seconds: Never suggest retrying in less than this.
        maximum_seconds: Never suggest waiting longer than this;
            if the engine would need longer, the caller should
            probably reset or give up.
    """
    cfg = engine.config
    target = target_pressure
    if target is None:
        target = max(0.0, cfg.escalation_threshold - 0.1)

    current = engine.pressure
    if current <= target:
        return minimum_seconds

    excess = current - target
    # Per-step dissipation doesn't have a direct time equivalent;
    # assume a step is taken no faster than once per second in the worst
    # case, so per_step counts once per second. Per-second dissipation
    # adds directly.
    per_second = cfg.dissipation_per_second + cfg.dissipation_per_step
    if per_second <= 0:
        # No passive dissipation: caller must reset before retry.
        return maximum_seconds

    seconds = excess / per_second
    return max(minimum_seconds, min(maximum_seconds, seconds))


class CircuitBreakerOpen(RuntimeError):
    """Raised when a call is attempted while the breaker is in the open state."""


@dataclass
class BreakerState:
    state: str  # "closed" | "open" | "half_open"
    failures: int
    opened_at: float  # 0.0 if not open
    last_failure_at: float


class CircuitBreaker:
    """Thread-safe circuit breaker for wrapping flaky downstream calls.

    Three states:
        - closed:    calls pass through; failures are counted.
        - open:      calls short-circuit with CircuitBreakerOpen until
                     cooldown expires.
        - half_open: after cooldown, one probe call is allowed. If it
                     succeeds, state returns to closed. If it fails, the
                     breaker re-opens with a fresh cooldown.

    Failure policy:
        A failure is counted when `call()` is invoked on a function that
        raises one of `failure_exceptions` (default: any Exception). Any
        other exception (e.g., `KeyboardInterrupt`) passes through
        without affecting breaker state.

    Example:
        breaker = CircuitBreaker(failure_threshold=5, cooldown_seconds=30.0)
        try:
            result = breaker.call(lambda: requests.get(url).json())
        except CircuitBreakerOpen:
            # breaker is tripped; use a cached value or fallback
            result = cached_fallback()
    """

    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        cooldown_seconds: float = 30.0,
        failure_exceptions: tuple[type[BaseException], ...] = (Exception,),
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if cooldown_seconds < 0:
            raise ValueError("cooldown_seconds must be >= 0")
        self._threshold = failure_threshold
        self._cooldown = cooldown_seconds
        self._failure_excs = failure_exceptions
        self._clock = clock

        self._lock = threading.RLock()
        self._state = "closed"
        self._failures = 0
        self._opened_at = 0.0
        self._last_failure_at = 0.0

    @property
    def state(self) -> str:
        """Current state — may transition from open→half_open on read."""
        with self._lock:
            self._maybe_transition_to_half_open()
            return self._state

    def snapshot(self) -> BreakerState:
        with self._lock:
            self._maybe_transition_to_half_open()
            return BreakerState(
                state=self._state,
                failures=self._failures,
                opened_at=self._opened_at,
                last_failure_at=self._last_failure_at,
            )

    def _maybe_transition_to_half_open(self) -> None:
        if self._state == "open":
            if self._clock() - self._opened_at >= self._cooldown:
                self._state = "half_open"

    def call(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Invoke `fn(*args, **kwargs)` through the breaker."""
        with self._lock:
            self._maybe_transition_to_half_open()
            if self._state == "open":
                raise CircuitBreakerOpen(
                    f"breaker open; cooldown "
                    f"{self._cooldown - (self._clock() - self._opened_at):.1f}s "
                    f"remaining"
                )

        try:
            result = fn(*args, **kwargs)
        except self._failure_excs as exc:
            self._record_failure()
            raise
        else:
            self._record_success()
            return result

    def _record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            self._last_failure_at = self._clock()
            if self._state == "half_open":
                # Probe failed; re-open.
                self._state = "open"
                self._opened_at = self._clock()
                self._failures = self._threshold  # stays "over threshold"
            elif self._failures >= self._threshold:
                self._state = "open"
                self._opened_at = self._clock()

    def _record_success(self) -> None:
        with self._lock:
            if self._state == "half_open":
                # Probe succeeded; close.
                self._state = "closed"
                self._failures = 0
                self._opened_at = 0.0
            elif self._state == "closed":
                # Steady-state success; reset failure counter.
                self._failures = 0

    def reset(self) -> None:
        """Force the breaker back to closed state. Useful for ops
        intervention (e.g., after verifying a downstream is healthy)."""
        with self._lock:
            self._state = "closed"
            self._failures = 0
            self._opened_at = 0.0
