"""Core pressure-accumulation model.

The pressure model tracks cost accumulation for an agent execution. Pressure rises
with each operation (tokens generated, tools called, planning steps taken) and
decays over time (dissipation). When pressure crosses the release threshold, the
engine signals that a reset is required.

The pressure engine is IAIso's runtime rate-limiting primitive. It composes
with higher-level controls (Layer 0 process/hardware anchors, Layer 4
human-in-the-loop escalation, Layer 6 existential safeguards) as specified
in the framework. Coefficients are configuration — calibrate them for the
target workload using `iaiso.evaluation`. See `../../../spec/pressure/README.md`
for the normative specification.
"""

from __future__ import annotations

import logging
import math
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from iaiso.audit import AuditEvent, AuditSink, NullSink

logger = logging.getLogger("iaiso")

ENFORCEMENT_PERMISSIVE = "permissive"
ENFORCEMENT_STRICT = "strict"

#: Coefficient set shipped with the library. Matching it exactly means nobody
#: has calibrated anything.
_LIBRARY_DEFAULT_COEFFICIENTS = {  # nosec B105 -- "token_coefficient" is not a password
    "token_coefficient": 0.015,
    "tool_coefficient": 0.08,
    "depth_coefficient": 0.05,
    "dissipation_per_step": 0.02,
    "dissipation_per_second": 0.0,
    "escalation_threshold": 0.85,
    "release_threshold": 0.95,
}

_warned: set[str] = set()


class StrictModeError(ValueError):
    """Raised when `enforcement_mode="strict"` refuses a degraded config.

    Fail closed. A safety framework whose gates silently do nothing is worse
    than no framework, because it produces confidence.
    """


def _degraded(condition: str, message: str, mode: str) -> None:
    """Refuse under strict; warn once per process under permissive."""
    if mode == ENFORCEMENT_STRICT:
        raise StrictModeError(f"iaiso: strict mode — {message}")
    if condition not in _warned:
        _warned.add(condition)
        logger.warning("iaiso: %s", message)


class Lifecycle(str, Enum):
    """Lifecycle states for a pressure-bounded execution."""

    INIT = "init"
    RUNNING = "running"
    ESCALATED = "escalated"
    RELEASED = "released"
    LOCKED = "locked"


class StepOutcome(str, Enum):
    """Outcome returned from `PressureEngine.step()`."""

    OK = "ok"
    ESCALATED = "escalated"
    RELEASED = "released"
    LOCKED = "locked"


@dataclass(frozen=True)
class PressureConfig:
    """Configuration for the pressure model.

    All coefficients have explicit units and defaults that should be treated as
    placeholders. Real deployments must calibrate these against measured workload
    behavior. See `iaiso.evaluation.calibrate`.

    Attributes:
        escalation_threshold: Pressure level at which the engine signals that human
            review or intervention is needed. Range [0.0, 1.0]. Default 0.85.
        release_threshold: Pressure level at which the engine forces a state reset.
            Must be > escalation_threshold. Range [0.0, 1.0]. Default 0.95.
        dissipation_per_step: Amount of pressure that decays per step, independent
            of wall-clock time. Default 0.02.
        dissipation_per_second: Additional decay rate based on elapsed wall time
            between steps. Set to 0.0 to use step-count dissipation only. Default 0.0.
        token_coefficient: Pressure added per 1000 tokens generated. Default 0.015.
        tool_coefficient: Pressure added per tool call. Default 0.08.
        depth_coefficient: Pressure added per level of planning/recursion depth.
            Default 0.05.
        post_release_lock: If True, the engine refuses further steps after a release
            until explicitly reset via `reset()`. If False, pressure continues
            accumulating from zero. Default True.
    """

    escalation_threshold: float = 0.85
    release_threshold: float = 0.95
    dissipation_per_step: float = 0.02
    dissipation_per_second: float = 0.0
    token_coefficient: float = 0.015
    tool_coefficient: float = 0.08
    depth_coefficient: float = 0.05
    post_release_lock: bool = True

    model_costs: dict[str, float] | None = field(default=None, hash=False)
    """USD per 1M tokens, keyed by model name. When set, `engine.step` events
    carry a `spend_usd` field. Cost is a readout; pressure is the control.

    Excluded from `__hash__` (a dict is unhashable) but not from `__eq__`:
    `PressureConfig` was hashable before this field existed and must stay so.
    Equal configs still hash equal, so the hash/eq contract holds."""

    budget_usd: float = 0.0
    """Hard spend ceiling in USD; 0 disables. Exceeding it reuses the existing
    lock path — no new lifecycle state, so the wire format stays frozen."""

    empty_step_dissipation: bool = False
    """2.0 default False: `dissipation_per_step` applies only to steps that carry
    work (tokens, tool calls or depth), so a caller cannot drain pressure by
    reporting empty steps. `PressureConfig.v1()` sets True (the 1.x behaviour the
    1.x vectors pin)."""

    unpriced_model_usd_per_million: float | None = None
    """Price for a step whose model is missing or not in `model_costs`.
    2.0 default None means fail closed: charge the highest price in
    `model_costs`. Set a number to charge that rate instead; 0.0 makes unpriced
    models free (the 1.x behaviour, which `PressureConfig.v1()` selects)."""

    max_total_tokens: int = 0
    """Lifetime token allowance for the execution; 0 disables. Unlike pressure
    this never decays and is not cleared by a release, so slow, steady work
    cannot run forever under the thresholds. Exhaustion locks the engine."""

    max_total_tool_calls: int = 0
    """Lifetime tool-call allowance; 0 disables. Same semantics as `max_total_tokens`."""

    max_total_steps: int = 0
    """Lifetime step allowance; 0 disables. Same semantics as `max_total_tokens`."""

    @classmethod
    def v1(cls, **overrides: Any) -> PressureConfig:
        """Config with IAIso 1.x semantics: empty steps dissipate and unpriced
        models are free. For replaying 1.x vectors and for migrations only."""
        base: dict[str, Any] = {"empty_step_dissipation": True,
                                "unpriced_model_usd_per_million": 0.0}
        base.update(overrides)
        return cls(**base)

    @property
    def has_total_cap(self) -> bool:
        """True when something bounds the execution's lifetime work."""
        return bool(self.max_total_tokens or self.max_total_tool_calls
                    or self.max_total_steps or (self.budget_usd > 0 and self.model_costs))

    def is_default_coefficients(self) -> bool:
        """True when nothing has been calibrated away from library defaults."""
        return all(
            getattr(self, name) == value
            for name, value in _LIBRARY_DEFAULT_COEFFICIENTS.items()
        )

    def __post_init__(self) -> None:
        if not 0.0 <= self.escalation_threshold <= 1.0:
            raise ValueError("escalation_threshold must be in [0, 1]")
        if not 0.0 <= self.release_threshold <= 1.0:
            raise ValueError("release_threshold must be in [0, 1]")
        if self.release_threshold <= self.escalation_threshold:
            raise ValueError("release_threshold must exceed escalation_threshold")
        for name in ("dissipation_per_step", "dissipation_per_second",
                     "token_coefficient", "tool_coefficient", "depth_coefficient"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.budget_usd < 0:
            raise ValueError("budget_usd must be non-negative")
        for model, price in (self.model_costs or {}).items():
            if price < 0:
                raise ValueError(f"model_costs[{model!r}] must be non-negative")
        for name in ("max_total_tokens", "max_total_tool_calls", "max_total_steps"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int) or v < 0:
                raise ValueError(f"{name} must be a non-negative int")
        for name in ("escalation_threshold", "release_threshold", "dissipation_per_step",
                     "dissipation_per_second", "token_coefficient", "tool_coefficient",
                     "depth_coefficient", "budget_usd"):
            if not math.isfinite(getattr(self, name)):
                raise ValueError(f"{name} must be finite")
        for model, price in (self.model_costs or {}).items():
            if not math.isfinite(price):
                raise ValueError(f"model_costs[{model!r}] must be finite")
        if self.unpriced_model_usd_per_million is not None and not (
                math.isfinite(self.unpriced_model_usd_per_million)
                and self.unpriced_model_usd_per_million >= 0):
            raise ValueError("unpriced_model_usd_per_million must be finite and non-negative")


@dataclass
class StepInput:
    """Single unit of work to account for pressure."""

    tokens: int = 0
    tool_calls: int = 0
    depth: int = 0
    tag: str | None = None
    """Optional string tag propagated into audit events, e.g. the operation name."""
    model: str | None = None
    """Model name used to price `tokens` against `PressureConfig.model_costs`.
    An unpriced model costs nothing — it is not an error, it is unmetered —
    unless `PressureConfig.unpriced_model_usd_per_million` is set."""

    def __post_init__(self) -> None:
        # Negative, fractional, NaN or boolean counts would lower pressure or
        # poison it (NaN clamps to 0.0). Work is a non-negative integer count.
        for name in ("tokens", "tool_calls", "depth"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise ValueError(f"StepInput.{name} must be an int, got {type(v).__name__}")
            if v < 0:
                raise ValueError(f"StepInput.{name} must be >= 0, got {v}")


@dataclass
class PressureSnapshot:
    """Immutable view of the engine state at a point in time."""

    pressure: float
    step: int
    lifecycle: Lifecycle
    last_delta: float
    last_step_at: float


@dataclass(frozen=True)
class Reservation:
    """Work set aside by `PressureEngine.reserve()` before it is done."""

    id: str
    tokens: int
    tool_calls: int
    usd: float


class ReservationRefused(RuntimeError):
    """`reserve()` refused: the work would exceed a cap or budget, or the
    engine is locked. `reason` is one of locked, tokens, tool_calls, steps,
    budget."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


class PressureEngine:
    """Tracks pressure accumulation for a single bounded execution.

    The engine is single-threaded and stateful. For concurrent executions, create
    one engine per execution. For shared cross-execution limits, see
    `iaiso.core.shared.SharedPressureCoordinator` (not yet implemented).

    Example:
        >>> cfg = PressureConfig()
        >>> engine = PressureEngine(cfg, execution_id="exec-123")
        >>> outcome = engine.step(StepInput(tokens=500, tool_calls=1))
        >>> if outcome is StepOutcome.ESCALATED:
        ...     # pause and request human review
        ...     pass
    """

    def __init__(
        self,
        config: PressureConfig,
        execution_id: str,
        audit_sink: AuditSink | None = None,
        clock: Any = time.monotonic,
        enforcement_mode: str = ENFORCEMENT_PERMISSIVE,
        calibration_artifact: str | None = None,
        consent_algorithm: str | None = None,
        consent_key_auto_generated: bool = False,
    ) -> None:
        if enforcement_mode not in (ENFORCEMENT_PERMISSIVE, ENFORCEMENT_STRICT):
            raise ValueError(
                f"enforcement_mode must be 'permissive' or 'strict', "
                f"got {enforcement_mode!r}"
            )
        self._enforcement_mode = enforcement_mode

        # Boot guard. Runs BEFORE any state exists, so a strict refusal leaves
        # nothing half-constructed behind.
        self._boot_guard(
            config=config,
            audit_sink=audit_sink,
            calibration_artifact=calibration_artifact,
            consent_algorithm=consent_algorithm,
            consent_key_auto_generated=consent_key_auto_generated,
        )

        self._cfg = config
        self._execution_id = execution_id
        self._audit = audit_sink or NullSink()
        self._clock = clock

        self._pressure: float = 0.0
        self._step: int = 0
        self._lifecycle: Lifecycle = Lifecycle.INIT
        self._last_delta: float = 0.0
        self._last_step_at: float = self._clock()
        self._spend_usd: float = 0.0
        self._total_tokens: int = 0
        self._total_tool_calls: int = 0
        self._total_steps: int = 0
        self._reservations: dict[str, Reservation] = {}
        self._lock = threading.RLock()

        self._emit("engine.init", pressure=self._pressure)

    def _boot_guard(
        self,
        config: PressureConfig,
        audit_sink: AuditSink | None,
        calibration_artifact: str | None,
        consent_algorithm: str | None,
        consent_key_auto_generated: bool,
    ) -> None:
        """Refuse (strict) or warn (permissive) on each degraded condition.

        Every message names the failing condition and the two ways out, because
        an operator reading it at 3am needs the remedy, not a diagnosis.
        """
        mode = self._enforcement_mode

        if consent_algorithm == "HS256" and consent_key_auto_generated:
            _degraded(
                "consent_autogen_hs256",
                "consent algorithm is HS256 and the signing key was "
                "auto-generated; no other party can verify these tokens. "
                "Supply a key, switch to RS256, or set "
                "enforcement_mode: permissive.",
                mode,
            )

        if audit_sink is None or isinstance(audit_sink, NullSink):
            _degraded(
                "null_sink",
                "audit sink is NullSink; escalations would be unobservable. "
                "Configure a sink or set enforcement_mode: permissive.",
                mode,
            )

        if not config.post_release_lock:
            _degraded(
                "post_release_lock_false",
                "post_release_lock is false; a released execution resumes "
                "immediately. Set post_release_lock: true or set "
                "enforcement_mode: permissive.",
                mode,
            )

        if config.is_default_coefficients() and not calibration_artifact:
            _degraded(
                "uncalibrated_defaults",
                "coefficients are at library defaults and no calibration "
                "artifact is present; thresholds will either never fire or "
                "fire constantly. Calibrate, or set "
                "enforcement_mode: permissive.",
                mode,
            )

        if not config.has_total_cap:
            _degraded(
                "no_total_cap",
                "no lifetime cap is set (max_total_tokens, max_total_tool_calls, "
                "max_total_steps, or budget_usd with model_costs); pressure "
                "decays, so steady work under the thresholds is unbounded. "
                "Set a cap or set enforcement_mode: permissive.",
                mode,
            )

        if config.budget_usd > 0 and not config.model_costs:
            _degraded(
                "budget_without_prices",
                "budget_usd is set but model_costs is empty, so spend is always "
                "0 and the budget can never trip. Set model_costs or set "
                "enforcement_mode: permissive.",
                mode,
            )

    @property
    def enforcement_mode(self) -> str:
        return self._enforcement_mode

    @property
    def spend_usd(self) -> float:
        """Cumulative USD spent by this execution, per `model_costs`."""
        return self._spend_usd

    @property
    def totals(self) -> dict[str, int]:
        """Lifetime work accounted so far. Not decayed, not cleared by a release."""
        return {"tokens": self._total_tokens, "tool_calls": self._total_tool_calls,
                "steps": self._total_steps}

    @property
    def config(self) -> PressureConfig:
        return self._cfg

    @property
    def execution_id(self) -> str:
        return self._execution_id

    @property
    def pressure(self) -> float:
        return self._pressure

    @property
    def lifecycle(self) -> Lifecycle:
        return self._lifecycle

    def snapshot(self) -> PressureSnapshot:
        return PressureSnapshot(
            pressure=self._pressure,
            step=self._step,
            lifecycle=self._lifecycle,
            last_delta=self._last_delta,
            last_step_at=self._last_step_at,
        )

    def step(self, work: StepInput) -> StepOutcome:
        """Account for a unit of work and advance the engine.

        Returns:
            OK: Pressure is below the escalation threshold. Continue normally.
            ESCALATED: Pressure crossed the escalation threshold. The caller
                should pause and request human review or take its configured
                escalation action. Further steps are still accepted.
            RELEASED: Pressure crossed the release threshold. State has been
                wiped. If `post_release_lock` is True, the engine is now LOCKED
                and will reject further steps until `reset()` is called.
            LOCKED: The engine is in the post-release locked state and refused
                this step. The caller must call `reset()` before continuing.
        """
        with self._lock:
            return self._step_locked(work)

    def _step_locked(self, work: StepInput) -> StepOutcome:
        if self._lifecycle is Lifecycle.LOCKED:
            self._emit("engine.step.rejected",
                       reason="locked",
                       requested_tokens=work.tokens,
                       requested_tools=work.tool_calls)
            return StepOutcome.LOCKED
        already = self._exhausted_cap()
        if already is not None:
            # Reset with clear_spend=False left a cap exhausted: refuse the work
            # instead of doing it and locking afterwards.
            return self._lock_for_cap(already)

        now = self._clock()
        elapsed = max(0.0, now - self._last_step_at)

        delta = (
            (work.tokens / 1000.0) * self._cfg.token_coefficient
            + work.tool_calls * self._cfg.tool_coefficient
            + work.depth * self._cfg.depth_coefficient
        )
        carries_work = work.tokens > 0 or work.tool_calls > 0 or work.depth > 0
        per_step = (self._cfg.dissipation_per_step
                    if (carries_work or self._cfg.empty_step_dissipation) else 0.0)
        decay = per_step + elapsed * self._cfg.dissipation_per_second

        # Inputs are validated non-negative ints and config values finite, so
        # this sum cannot be NaN. nosemgrep: clamp-swallows-nan
        self._pressure = max(0.0, min(1.0, self._pressure + delta - decay))  # nosemgrep: clamp-swallows-nan
        self._step += 1
        self._last_delta = delta - decay
        self._last_step_at = now
        self._lifecycle = Lifecycle.RUNNING

        step_spend = self._price(work)
        self._spend_usd += step_spend
        self._total_tokens += work.tokens
        self._total_tool_calls += work.tool_calls
        self._total_steps += 1

        event_data: dict[str, Any] = dict(
            step=self._step,
            pressure=self._pressure,
            delta=delta,
            decay=decay,
            tokens=work.tokens,
            tool_calls=work.tool_calls,
            depth=work.depth,
            tag=work.tag,
        )
        # `spend_usd` appears only when prices are configured, so consumers of
        # the frozen 1.0 envelope never see a key they did not opt into.
        if self._cfg.model_costs:
            event_data["spend_usd"] = self._spend_usd
        self._emit("engine.step", **event_data)

        # Budget exhaustion reuses the existing lock path. No new lifecycle
        # state: the wire format is frozen.
        if self._cfg.budget_usd > 0 and self._spend_usd >= self._cfg.budget_usd:
            return self._lock_for_budget()
        exhausted = self._exhausted_cap()
        if exhausted is not None:
            return self._lock_for_cap(exhausted)

        if self._pressure >= self._cfg.release_threshold:
            return self._release()
        if self._pressure >= self._cfg.escalation_threshold:
            self._lifecycle = Lifecycle.ESCALATED
            self._emit("engine.escalation",
                       pressure=self._pressure,
                       threshold=self._cfg.escalation_threshold)
            return StepOutcome.ESCALATED
        return StepOutcome.OK

    def _exhausted_cap(self) -> str | None:
        cfg = self._cfg
        for name, total, cap in (("tokens", self._total_tokens, cfg.max_total_tokens),
                                 ("tool_calls", self._total_tool_calls, cfg.max_total_tool_calls),
                                 ("steps", self._total_steps, cfg.max_total_steps)):
            if cap and total >= cap:
                return name
        return None

    def _lock_for_cap(self, which: str) -> StepOutcome:
        self._pressure = 0.0
        self._lifecycle = Lifecycle.LOCKED
        self._emit("engine.locked", reason="cap_exceeded", cap=which,
                   totals=self.totals)
        return StepOutcome.LOCKED

    def _price(self, work: StepInput, *, emit: bool = True) -> float:
        """USD for this step. With no `model_costs` nothing is priced. A missing
        or unknown model is charged `unpriced_model_usd_per_million`, or the
        highest configured price when that is None (fail closed)."""
        costs = self._cfg.model_costs
        if not costs or work.tokens == 0:
            return 0.0
        price_per_million = costs.get(work.model) if work.model is not None else None
        if price_per_million is None:
            fallback = self._cfg.unpriced_model_usd_per_million
            if fallback is None:
                fallback = max(costs.values())
            price_per_million = fallback
            if emit:
                self._emit("engine.unpriced_model", model=work.model,
                           usd_per_million=fallback)
        return (work.tokens / 1_000_000.0) * price_per_million

    def price(self, work: StepInput) -> float:
        """USD this step would cost, without accounting it. Lets a caller refuse
        work before doing it: `engine.spend_usd + engine.price(w) > budget`."""
        return self._price(work, emit=False)

    # --- reserve / commit -------------------------------------------------

    def reserve(self, estimate: StepInput) -> Reservation:
        """Set aside the most this work can cost before doing it.

        Refuses (raises `ReservationRefused`) when the engine is locked or when
        lifetime totals plus outstanding reservations plus `estimate` would
        exceed a cap or the budget. Concurrent callers cannot overspend: each
        reservation counts against the allowance until `commit` or `cancel`.
        """
        with self._lock:
            if self._lifecycle is Lifecycle.LOCKED:
                raise ReservationRefused("locked", "engine is locked; reset() required")
            cfg = self._cfg
            held = list(self._reservations.values())
            r_tokens = sum(r.tokens for r in held) + estimate.tokens
            r_tools = sum(r.tool_calls for r in held) + estimate.tool_calls
            r_usd = sum(r.usd for r in held)
            usd = self._price(estimate, emit=False)
            checks = (
                ("tokens", cfg.max_total_tokens, self._total_tokens + r_tokens),
                ("tool_calls", cfg.max_total_tool_calls, self._total_tool_calls + r_tools),
                ("steps", cfg.max_total_steps, self._total_steps + len(held) + 1),
            )
            for name, cap, would in checks:
                if cap and would > cap:
                    self._emit("engine.reservation.refused", reason=name,
                               cap=cap, would_be=would)
                    raise ReservationRefused(name, f"{name}: {would} would exceed cap {cap}")
            if cfg.budget_usd > 0 and self._spend_usd + r_usd + usd > cfg.budget_usd:
                self._emit("engine.reservation.refused", reason="budget",
                           budget_usd=cfg.budget_usd,
                           would_be_usd=self._spend_usd + r_usd + usd)
                raise ReservationRefused(
                    "budget", f"budget: ${self._spend_usd + r_usd + usd:.6f} would exceed "
                              f"${cfg.budget_usd:.6f}")
            res = Reservation(id=uuid.uuid4().hex, tokens=estimate.tokens,
                              tool_calls=estimate.tool_calls, usd=usd)
            self._reservations[res.id] = res
            self._emit("engine.reservation", id=res.id, tokens=res.tokens,
                       tool_calls=res.tool_calls, usd=res.usd)
            return res

    def commit(self, reservation: Reservation, actual: StepInput) -> StepOutcome:
        """Replace a reservation with the work actually done, and step it.
        An overrun is still accounted (and can lock); it is also audited."""
        with self._lock:
            if self._reservations.pop(reservation.id, None) is None:
                raise KeyError(f"unknown or already settled reservation {reservation.id}")
            if actual.tokens > reservation.tokens or actual.tool_calls > reservation.tool_calls:
                self._emit("engine.reservation.overrun", id=reservation.id,
                           reserved_tokens=reservation.tokens, actual_tokens=actual.tokens,
                           reserved_tool_calls=reservation.tool_calls,
                           actual_tool_calls=actual.tool_calls)
            return self._step_locked(actual)

    def cancel(self, reservation: Reservation) -> None:
        """Return a reservation that was not used (the call failed or was refused)."""
        with self._lock:
            if self._reservations.pop(reservation.id, None) is not None:
                self._emit("engine.reservation.cancelled", id=reservation.id)

    @property
    def outstanding_reservations(self) -> int:
        return len(self._reservations)

    @property
    def budget_remaining_usd(self) -> float | None:
        """None when no budget is set."""
        if self._cfg.budget_usd <= 0:
            return None
        return max(0.0, self._cfg.budget_usd - self._spend_usd)

    def _lock_for_budget(self) -> StepOutcome:
        self._pressure = 0.0
        self._lifecycle = Lifecycle.LOCKED
        self._emit("engine.locked",
                   reason="budget_exceeded",
                   spend_usd=self._spend_usd,
                   budget_usd=self._cfg.budget_usd)
        return StepOutcome.LOCKED

    def _release(self) -> StepOutcome:
        prior_pressure = self._pressure
        self._lifecycle = Lifecycle.RELEASED
        self._emit("engine.release",
                   pressure=prior_pressure,
                   threshold=self._cfg.release_threshold)

        self._pressure = 0.0
        if self._cfg.post_release_lock:
            self._lifecycle = Lifecycle.LOCKED
            self._emit("engine.locked", reason="post_release_lock")
        else:
            self._lifecycle = Lifecycle.RUNNING

        return StepOutcome.RELEASED

    def reset(self, *, clear_spend: bool = True, by: str | None = None) -> PressureSnapshot:
        """Clear pressure and unlock the engine. Emits an audit event.

        By default spend and lifetime totals are cleared with the rest of the
        state: a reset is a human deciding this execution starts over, budget
        included. Pass `clear_spend=False` when the person resetting may unlock
        the execution but not refill its budget or caps (an exhausted cap then
        locks again on the next step). `by` is recorded in the audit event.
        """
        with self._lock:
            return self._reset_locked(clear_spend=clear_spend, by=by)

    def _reset_locked(self, *, clear_spend: bool, by: str | None) -> PressureSnapshot:
        self._pressure = 0.0
        self._step = 0
        self._last_delta = 0.0
        self._last_step_at = self._clock()
        self._lifecycle = Lifecycle.INIT
        if clear_spend:
            self._spend_usd = 0.0
            self._total_tokens = 0
            self._total_tool_calls = 0
            self._total_steps = 0
        extra: dict[str, Any] = {}
        if by is not None:
            extra["by"] = by
        if not clear_spend:
            extra["spend_kept_usd"] = self._spend_usd
            extra["totals_kept"] = self.totals
        self._emit("engine.reset", pressure=self._pressure, **extra)
        return self.snapshot()

    def _emit(self, kind: str, **data: Any) -> None:
        self._audit.emit(AuditEvent(
            execution_id=self._execution_id,
            kind=kind,
            timestamp=time.time(),
            data=data,
        ))