"""PressureWrapper: put any agent inside a BoundedExecution with one line.

    from iaiso import PressureWrapper, JsonlFileSink

    safe_agent = PressureWrapper(
        your_agent,                  # LangChain, CrewAI, AutoGen or any object with run/invoke/kickoff, or a callable
        max_pressure=0.85,           # lock the agent when pressure reaches 85%
        audit_sink=JsonlFileSink("audit.jsonl"),
    )
    safe_agent.run("Your task here")

Each call to `run()` (or `invoke()`, `kickoff()`, calling the wrapper) does three things:

1. **Before the call** it refuses to start if the execution is locked
   (`ExecutionLocked`), or paused for review after an escalation
   (`PressureEscalated`, unless `on_escalation` says otherwise). If
   `required_scope` is set, the attached consent must grant it.
2. **The call** goes to the wrapped agent unchanged.
3. **After the call** it accounts for the work: tokens and tool calls are read
   from the result when the framework reports them (OpenAI, Anthropic,
   LangChain and dict-shaped results), or estimated from text length when it
   does not. The agent's result is always returned; if this call pushed pressure
   past a threshold, the *next* call is the one that is stopped.

Thresholds: `max_pressure` is the release threshold, where the engine wipes the
execution's pressure and, by default, locks it until a person calls `reset()`.
Escalation (pause for review) happens earlier, at `escalate_at`, which defaults
to 0.10 below `max_pressure`. Pass a full `PressureConfig` instead for complete
control; the coefficients still need calibrating for your workload
(`iaiso.calibration`), as the engine's boot guard will tell you.

`enable_backprop` is accepted for compatibility with earlier documentation. It
has no effect: no "back-propagation magnification" exists in the engine, and
the wrapper warns when the flag is set.
"""

from __future__ import annotations

import inspect
import warnings
from typing import Any, Callable, cast

from iaiso.audit import AuditSink
from iaiso.consent import ConsentScope
from iaiso.core.engine import (
    ENFORCEMENT_PERMISSIVE,
    Lifecycle,
    PressureConfig,
    PressureSnapshot,
    StepOutcome,
)
from iaiso.core.execution import BoundedExecution, ExecutionLocked

#: Methods tried, in order, when no `method` is given.
_SYNC_METHODS = ("run", "invoke", "kickoff", "__call__")
_ASYNC_METHODS = ("arun", "ainvoke", "kickoff_async")

#: Characters per token used when a result carries no usage data. A rough
#: average for English text; set `estimate_tokens=False` to turn estimating off.
_CHARS_PER_TOKEN = 4

EscalationPolicy = str | Callable[["PressureWrapper", PressureSnapshot], bool]


class PressureEscalated(RuntimeError):
    """The execution crossed its escalation threshold and is paused for review.

    Call `approve()` to let the next call through, or `reset()` to start over.
    """

    def __init__(self, message: str, snapshot: PressureSnapshot) -> None:
        super().__init__(message)
        self.snapshot = snapshot


def _get(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _usage_tokens(usage: Any) -> int:
    """Total tokens from a usage object or dict, whatever the provider calls them."""
    if usage is None:
        return 0
    total = _int(_get(usage, "total_tokens"))
    if total:
        return total
    return (
        _int(_get(usage, "input_tokens")) + _int(_get(usage, "output_tokens"))
        or _int(_get(usage, "prompt_tokens")) + _int(_get(usage, "completion_tokens"))
    )


def extract_usage(result: Any) -> tuple[int, int]:
    """Return (tokens, tool_calls) reported by `result`, or (0, 0) if none.

    Understands OpenAI and Anthropic response objects (`.usage`), LangChain
    messages (`.usage_metadata`, `.tool_calls`), LangChain agent outputs
    (`intermediate_steps`) and plain dicts using any of those keys.
    """
    tokens = 0
    for key in ("usage", "usage_metadata", "token_usage"):
        tokens = _usage_tokens(_get(result, key))
        if tokens:
            break
    if not tokens:
        llm_output = _get(result, "llm_output")
        if llm_output is not None:
            tokens = _usage_tokens(_get(llm_output, "token_usage"))

    tool_calls = 0
    for key in ("tool_calls", "intermediate_steps"):
        calls = _get(result, key)
        if isinstance(calls, (list, tuple)):
            tool_calls = len(calls)
            break
    return tokens, tool_calls


def _estimate_tokens(*texts: Any) -> int:
    chars = sum(len(t) if isinstance(t, str) else len(str(t)) for t in texts if t is not None)
    return max(1, chars // _CHARS_PER_TOKEN) if chars else 0


class PressureWrapper:
    """Wrap an agent so every call is accounted for and bounded by IAIso.

    Args:
        agent: The agent. Any object with `run`, `invoke`, `kickoff` or
            `__call__` (tried in that order), or a plain function.
        max_pressure: Release threshold in (0, 1]. Ignored if `config` is given.
        escalate_at: Escalation threshold, below `max_pressure`. Defaults to
            `max_pressure - 0.10`. Ignored if `config` is given.
        config: A full `PressureConfig`, for calibrated deployments.
        audit_sink: Where audit events go. Without one, nobody can see
            escalations; the engine warns (permissive) or refuses (strict).
        consent: A verified `ConsentScope` to attach to the execution.
        required_scope: Scope the consent must grant before each call.
        on_escalation: What to do when a call starts while escalated:
            `"raise"` (default) raises `PressureEscalated` until someone calls
            `approve()` or `reset()`; `"continue"` records the event and goes
            on; or a function `(wrapper, snapshot) -> bool` that returns True
            to proceed.
        enforcement_mode: `"permissive"` (default) or `"strict"`, passed to the
            engine's boot guard.
        method: Name of the agent method to call, to skip auto-detection.
        token_counter: Function `(task, result) -> int` used when the result
            carries no usage data.
        estimate_tokens: Estimate tokens from text length when neither the
            result nor `token_counter` reports them. Default True, so an
            agent that reports nothing is still bounded.
        model: Model name used to price tokens against `config.model_costs`.
        execution_id: Fixed id for the execution (a UUID is generated otherwise).
        agent_factory: Zero-argument function that builds a fresh agent. When
            given, a release (or `reset()`) throws the current agent away —
            its memory, scratchpad and conversation go with it — and the next
            call runs on a new one. Without it a release only zeroes the
            pressure number while the agent keeps everything it accumulated,
            and the wrapper records `wrapper.agent_state_kept`. Pass
            `agent=None` to build the first agent from the factory too.
        enable_backprop: Accepted for compatibility; has no effect.
    """

    def __init__(
        self,
        agent: Any,
        *,
        max_pressure: float = 0.95,
        escalate_at: float | None = None,
        config: PressureConfig | None = None,
        audit_sink: AuditSink | None = None,
        consent: ConsentScope | None = None,
        required_scope: str | None = None,
        on_escalation: EscalationPolicy = "raise",
        enforcement_mode: str = ENFORCEMENT_PERMISSIVE,
        method: str | None = None,
        token_counter: Callable[[Any, Any], int] | None = None,
        estimate_tokens: bool = True,
        model: str | None = None,
        execution_id: str | None = None,
        enable_backprop: bool = False,
        calibration_artifact: str | None = None,
        agent_factory: Callable[[], Any] | None = None,
    ) -> None:
        if enable_backprop:
            warnings.warn(
                "iaiso: enable_backprop has no effect. The engine has no "
                "back-propagation or quality magnification; remove the argument.",
                DeprecationWarning,
                stacklevel=2,
            )
        if isinstance(on_escalation, str) and on_escalation not in ("raise", "continue"):
            raise ValueError("on_escalation must be 'raise', 'continue' or a function")

        if agent is None and agent_factory is None:
            raise TypeError("give an agent, an agent_factory, or both")
        if agent_factory is not None and not callable(agent_factory):
            raise TypeError("agent_factory must be callable")
        self._factory = agent_factory
        self._method = method
        self._agent: Any = None
        self._call: Callable[..., Any] | None = None
        self._acall: Callable[..., Any] | None = None
        self.agent_generation = 0
        if agent is None:
            agent = agent_factory()  # type: ignore[misc]  # checked above: one of the two is set
        self._bind(agent)
        self._required_scope = required_scope
        self._on_escalation = on_escalation
        self._token_counter = token_counter
        self._estimate = estimate_tokens
        self._model = model
        self._approved_once = False
        self.last_outcome: StepOutcome | None = None

        self.execution = BoundedExecution.start(
            execution_id=execution_id,
            config=config or self._config_for(max_pressure, escalate_at),
            consent=consent,
            audit_sink=audit_sink,
            enforcement_mode=enforcement_mode,
            calibration_artifact=calibration_artifact,
        )

    # ------------------------------------------------------------------ setup

    def _bind(self, agent: Any) -> None:
        self._call = self._resolve(agent, self._method, _SYNC_METHODS)
        self._acall = self._resolve(agent, None, _ASYNC_METHODS, required=False)
        self._agent = agent
        self.agent_generation += 1

    def _discard_agent(self, reason: str) -> None:
        """Called after a release or reset. With a factory, drop every reference
        to the agent so its state cannot carry over; without one, say so."""
        if self._factory is None:
            self.execution._emit("wrapper.agent_state_kept", reason=reason,
                                 note="no agent_factory; the agent keeps its state")
            return
        self._agent = self._call = self._acall = None
        self.execution._emit("wrapper.agent_discarded", reason=reason,
                             generation=self.agent_generation)

    def _ensure_agent(self) -> None:
        if self._agent is None:
            if self._factory is None:  # unreachable: agents are only discarded when a factory exists
                raise RuntimeError("agent was discarded and no agent_factory is set")
            self._bind(self._factory())
            self.execution._emit("wrapper.agent_rebuilt", generation=self.agent_generation)

    @staticmethod
    def _config_for(max_pressure: float, escalate_at: float | None) -> PressureConfig:
        if not 0.0 < max_pressure <= 1.0:
            raise ValueError("max_pressure must be in (0, 1]")
        if escalate_at is None:
            escalate_at = max(0.0, round(max_pressure - 0.10, 6))
        # PressureConfig validates that release > escalation.
        return PressureConfig(escalation_threshold=escalate_at,
                              release_threshold=max_pressure)

    @staticmethod
    def _resolve(agent: Any, method: str | None, candidates: tuple[str, ...],
                 required: bool = True) -> Callable[..., Any] | None:
        if method is not None:
            fn = getattr(agent, method, None)
            if not callable(fn):
                raise TypeError(f"agent has no callable method {method!r}")
            return cast(Callable[..., Any], fn)
        for name in candidates:
            if name == "__call__":
                if callable(agent):
                    return cast(Callable[..., Any], agent)
                continue
            fn = getattr(agent, name, None)
            if callable(fn):
                return cast(Callable[..., Any], fn)
        if required:
            raise TypeError(
                f"cannot find how to call {type(agent).__name__}: give it one of "
                f"{', '.join(candidates[:-1])}, make it callable, or pass method="
            )
        return None

    # --------------------------------------------------------------- control

    def approve(self) -> None:
        """Let the next call through while escalated (a person has reviewed it)."""
        self._approved_once = True
        self.execution._emit("wrapper.escalation_approved",
                             pressure=self.execution.engine.pressure)

    def reset(self) -> PressureSnapshot:
        """Clear pressure and unlock. Use after a release lock or a review."""
        self._approved_once = False
        snap = self.execution.reset()
        if self._agent is not None:
            self._discard_agent("reset")
        return snap

    def snapshot(self) -> PressureSnapshot:
        return self.execution.snapshot()

    @property
    def pressure(self) -> float:
        return self.execution.engine.pressure

    @property
    def lifecycle(self) -> Lifecycle:
        return self.execution.engine.lifecycle

    def record_tool_call(self, name: str | None = None, count: int = 1,
                         tokens: int = 0) -> StepOutcome:
        """Let the agent's tools report themselves for finer accounting."""
        outcome = self.execution.record_tool_call(name=name, count=count, tokens=tokens)
        if outcome is StepOutcome.RELEASED:
            self._discard_agent("release")
        return outcome

    def close(self) -> None:
        self.execution.__exit__(None, None, None)

    def __enter__(self) -> "PressureWrapper":
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None,
                 tb: Any) -> None:
        self.execution.__exit__(exc_type, exc, tb)

    # ------------------------------------------------------------------ calls

    def _before(self) -> None:
        outcome = self.execution.check()
        if outcome is StepOutcome.LOCKED:
            raise ExecutionLocked(
                f"execution {self.execution.engine.execution_id} is locked; "
                "call reset() before continuing"
            )
        if outcome is StepOutcome.ESCALATED:
            snap = self.snapshot()
            if self._approved_once:
                self._approved_once = False
            elif self._on_escalation == "continue":
                self.execution._emit("wrapper.escalation_continued", pressure=snap.pressure)
            elif callable(self._on_escalation):
                if not self._on_escalation(self, snap):
                    self.execution._emit("wrapper.escalation_refused", pressure=snap.pressure)
                    raise PressureEscalated(
                        f"escalation handler refused the call at pressure {snap.pressure:.2f}",
                        snap)
            else:
                raise PressureEscalated(
                    f"pressure {snap.pressure:.2f} is above the escalation threshold; "
                    "call approve() to continue or reset() to start over",
                    snap)
        if self._required_scope:
            self.execution.require_scope(self._required_scope)
        self._ensure_agent()

    def _after(self, task: Any, result: Any) -> None:
        tokens, tool_calls = extract_usage(result)
        tag = "agent.call"
        if not tokens and self._token_counter is not None:
            tokens = _int(self._token_counter(task, result))
        if not tokens and self._estimate:
            tokens = _estimate_tokens(task, result)
            tag = "agent.call.estimated"
        try:
            self.last_outcome = self.execution.record_step(
                tokens=tokens, tool_calls=tool_calls, tag=tag, model=self._model)
        except ExecutionLocked:
            # The work already happened (for example, it used up the budget).
            # Return its result; the next call is the one refused.
            self.last_outcome = StepOutcome.LOCKED
        if self.last_outcome is StepOutcome.RELEASED:
            self._discard_agent("release")

    def run(self, *args: Any, **kwargs: Any) -> Any:
        """Call the wrapped agent under pressure control and return its result."""
        self._before()
        call = self._call
        if call is None:  # _before() rebuilds a discarded agent, so this is unreachable
            raise RuntimeError("no agent to call")
        result = call(*args, **kwargs)
        self._after(args[0] if args else kwargs, result)
        return result

    invoke = run
    kickoff = run
    __call__ = run

    async def arun(self, *args: Any, **kwargs: Any) -> Any:
        """Async version of `run()`, for agents with arun/ainvoke/kickoff_async."""
        self._before()
        fn = self._acall or self._call
        if fn is None:
            raise RuntimeError("no agent to call")
        result = fn(*args, **kwargs)
        if inspect.isawaitable(result):
            result = await result
        self._after(args[0] if args else kwargs, result)
        return result

    ainvoke = arun

    def __getattr__(self, name: str) -> Any:
        # Anything else (memory, tools, config) goes to the wrapped agent.
        if name.startswith("__") or name.startswith("_"):
            raise AttributeError(name)
        self._ensure_agent()
        return getattr(self._agent, name)

    def __repr__(self) -> str:
        kind = type(self._agent).__name__ if self._agent is not None else "<discarded>"
        return (f"PressureWrapper({kind}, "
                f"pressure={self.pressure:.2f}, lifecycle={self.lifecycle.value})")


class IAIsoPressureWrapper(PressureWrapper):
    """Alias using the argument names in the v5.0 integration spec.

    `pressure_threshold` maps to `max_pressure`, `consent_scope` to
    `required_scope`; `enable_magnification` is accepted and has no effect.
    """

    def __init__(self, agent: Any, *, pressure_threshold: float = 0.95,
                 enable_magnification: bool = False,
                 consent_scope: str | None = None, **kwargs: Any) -> None:
        if enable_magnification:
            warnings.warn(
                "iaiso: enable_magnification has no effect; remove the argument.",
                DeprecationWarning, stacklevel=2)
        super().__init__(agent, max_pressure=pressure_threshold,
                         required_scope=consent_scope, **kwargs)
