"""BoundedExecution — high-level abstraction combining engine + consent + audit.

This is the primary public API for embedding IAIso into an agent loop. A
BoundedExecution owns a PressureEngine, optionally a ConsentScope, and an
AuditSink. It exposes operations for accounting for work (`record_tokens`,
`record_tool_call`) and for controlling flow (`check`, `require_scope`).

Typical usage:

    with BoundedExecution.start(
        execution_id="exec-abc",
        config=PressureConfig(),
        consent=verified_scope,
        audit_sink=audit_sink,
    ) as exec:
        while not done:
            if exec.check() is StepOutcome.ESCALATED:
                escalate_to_human()
                exec.reset()  # or break, depending on policy
                continue
            exec.require_scope("tools.search")
            result = run_tool("search", query)
            exec.record_tool_call(name="search")
            exec.record_tokens(tokens=result.token_count, tag="search_result")
"""

from __future__ import annotations

import contextlib
import uuid
from dataclasses import dataclass
from types import TracebackType
from typing import Any, Iterator

from iaiso.audit import AuditEvent, AuditSink, NullSink
from iaiso.consent import ConsentScope, InsufficientScope
from iaiso.core.engine import (
    ENFORCEMENT_PERMISSIVE,
    Lifecycle,
    PressureConfig,
    PressureEngine,
    PressureSnapshot,
    StepInput,
    StepOutcome,
)


class ExecutionLocked(RuntimeError):
    """Raised when attempting to record work on a locked execution."""


class ScopeRequired(RuntimeError):
    """Raised when an operation requires a consent scope but none was attached."""


@dataclass
class BoundedExecution:
    """A bounded agent execution with integrated pressure, consent, and audit.

    Do not construct directly; use `BoundedExecution.start()` or `.attach()`.
    """

    engine: PressureEngine
    consent: ConsentScope | None
    audit_sink: AuditSink

    @classmethod
    def start(
        cls,
        *,
        execution_id: str | None = None,
        config: PressureConfig | None = None,
        consent: ConsentScope | None = None,
        audit_sink: AuditSink | None = None,
        enforcement_mode: str = ENFORCEMENT_PERMISSIVE,
        calibration_artifact: str | None = None,
        consent_algorithm: str | None = None,
        consent_key_auto_generated: bool = False,
    ) -> "BoundedExecution":
        """Create a fresh BoundedExecution.

        `enforcement_mode` is forwarded to the engine's boot guard. Under
        `"strict"` this raises `StrictModeError` rather than returning a
        degraded execution — a policy that says strict must mean strict at the
        entry point people actually use, not only when the engine is built by
        hand.
        """
        exec_id = execution_id or f"exec-{uuid.uuid4()}"
        cfg = config or PressureConfig()
        sink = audit_sink or NullSink()
        engine = PressureEngine(
            cfg,
            execution_id=exec_id,
            audit_sink=sink,
            enforcement_mode=enforcement_mode,
            calibration_artifact=calibration_artifact,
            consent_algorithm=consent_algorithm,
            consent_key_auto_generated=consent_key_auto_generated,
        )

        instance = cls(engine=engine, consent=consent, audit_sink=sink)
        if consent is not None:
            instance._emit("execution.consent_attached",
                           subject=consent.subject,
                           scopes=consent.scopes,
                           jti=consent.jti)
        return instance

    def record_tokens(
        self, tokens: int, *, tag: str | None = None, model: str | None = None
    ) -> StepOutcome:
        """Account for generated tokens.

        `model` prices those tokens against `PressureConfig.model_costs`.
        """
        return self._account(StepInput(tokens=tokens, tag=tag, model=model))

    def record_tool_call(
        self,
        *,
        name: str | None = None,
        count: int = 1,
        tokens: int = 0,
    ) -> StepOutcome:
        """Account for one or more tool calls, plus any tokens they returned."""
        return self._account(
            StepInput(tokens=tokens, tool_calls=count, tag=name)
        )

    def record_step(
        self,
        *,
        tokens: int = 0,
        tool_calls: int = 0,
        depth: int = 0,
        tag: str | None = None,
        model: str | None = None,
    ) -> StepOutcome:
        """Account for a generic unit of work."""
        return self._account(StepInput(
            tokens=tokens,
            tool_calls=tool_calls,
            depth=depth,
            tag=tag,
            model=model,
        ))

    @property
    def spend_usd(self) -> float:
        """Cumulative USD spent by this execution, per `model_costs`."""
        return self.engine.spend_usd

    def _account(self, work: StepInput) -> StepOutcome:
        outcome = self.engine.step(work)
        if outcome is StepOutcome.LOCKED:
            raise ExecutionLocked(
                f"execution {self.engine.execution_id} is locked; "
                "call reset() before continuing"
            )
        return outcome

    def check(self) -> StepOutcome:
        """Return the current outcome without accounting for new work.

        Useful as a guard at the top of an agent loop to detect escalation
        without double-counting.
        """
        lifecycle = self.engine.lifecycle
        if lifecycle is Lifecycle.LOCKED:
            return StepOutcome.LOCKED
        if lifecycle is Lifecycle.ESCALATED:
            return StepOutcome.ESCALATED
        return StepOutcome.OK

    def require_scope(self, scope: str) -> None:
        """Raise if no consent is attached or the attached consent does not grant `scope`.

        Emits a `consent.check` audit event on every call, successful or not.
        """
        if self.consent is None:
            self._emit("consent.missing", requested=scope)
            raise ScopeRequired(
                f"scope '{scope}' required but no consent attached"
            )
        try:
            self.consent.require(scope)
        except InsufficientScope as exc:
            self._emit("consent.denied",
                       requested=scope,
                       granted=self.consent.scopes,
                       jti=self.consent.jti)
            raise
        self._emit("consent.granted",
                   requested=scope,
                   jti=self.consent.jti)

    def reset(self) -> PressureSnapshot:
        return self.engine.reset()

    def snapshot(self) -> PressureSnapshot:
        return self.engine.snapshot()

    def _emit(self, kind: str, **data: Any) -> None:
        import time
        self.audit_sink.emit(AuditEvent(
            execution_id=self.engine.execution_id,
            kind=kind,
            timestamp=time.time(),
            data=data,
        ))

    def __enter__(self) -> "BoundedExecution":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._emit(
            "execution.closed",
            final_pressure=self.engine.pressure,
            final_lifecycle=self.engine.lifecycle.value,
            exception=type(exc).__name__ if exc else None,
        )