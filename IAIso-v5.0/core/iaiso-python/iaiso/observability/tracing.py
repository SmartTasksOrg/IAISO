"""Distributed tracing integration.

Wires `BoundedExecution` into OpenTelemetry so each execution — and each
step within it — becomes a span. Downstream services (LLM APIs, tool
calls, databases) that also emit OTel spans appear as children,
giving operators a single trace view of an agent run.

Usage:
    from opentelemetry import trace
    from iaiso.observability.tracing import TracedBoundedExecution

    tracer = trace.get_tracer("my-agent")
    with TracedBoundedExecution.start(
        tracer=tracer,
        config=PressureConfig(),
    ) as exec_:
        # The BoundedExecution is now wrapped in an OTel span named
        # "iaiso.execution". Every record_step() emits a child span
        # "iaiso.step" tagged with outcome and pressure.
        exec_.record_step(tokens=500)

Design:
    - `TracedBoundedExecution` is a thin wrapper around `BoundedExecution`
      that adds span lifecycle management. If OTel is not installed or
      no tracer is provided, it degrades to plain `BoundedExecution`
      with zero overhead.
    - Span attributes follow the draft semantic conventions for GenAI
      where applicable (https://opentelemetry.io/docs/specs/semconv/gen-ai/).
    - Exceptions during a span are recorded with `span.record_exception()`
      and set the span status to ERROR.

Install:
    pip install iaiso[otel]
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from iaiso.core import BoundedExecution, PressureConfig, StepInput, StepOutcome

try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode
    _OTEL_AVAILABLE = True
except ImportError:  # pragma: no cover
    _OTEL_AVAILABLE = False


class TracedBoundedExecution:
    """A `BoundedExecution` whose lifecycle is represented as OTel spans.

    Instances are produced by the `start()` classmethod so they can be
    used as context managers. Attributes on the wrapped execution are
    accessible via attribute proxy.
    """

    def __init__(self, execution: BoundedExecution, tracer: Any = None) -> None:
        self._exec = execution
        self._tracer = tracer
        self._exec_span: Any = None
        self._exec_span_cm: Any = None

    @classmethod
    def start(
        cls,
        *,
        tracer: Any = None,
        config: PressureConfig | None = None,
        **kwargs: Any,
    ) -> "TracedBoundedExecution":
        execution = BoundedExecution.start(config=config, **kwargs)
        return cls(execution, tracer=tracer)

    def __enter__(self) -> "TracedBoundedExecution":
        self._exec.__enter__()
        if self._tracer is not None and _OTEL_AVAILABLE:
            self._exec_span_cm = self._tracer.start_as_current_span(
                "iaiso.execution",
                attributes={
                    "iaiso.execution_id": self._exec.engine.execution_id,
                },
            )
            self._exec_span = self._exec_span_cm.__enter__()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        try:
            if self._exec_span is not None:
                snap = self._exec.snapshot()
                self._exec_span.set_attribute("iaiso.final_pressure", snap.pressure)
                self._exec_span.set_attribute("iaiso.final_lifecycle", snap.lifecycle.value)
                self._exec_span.set_attribute("iaiso.total_steps", snap.step)
                if exc_type is not None:
                    self._exec_span.record_exception(exc_val)
                    self._exec_span.set_status(Status(StatusCode.ERROR, str(exc_val)))
        finally:
            if self._exec_span_cm is not None:
                self._exec_span_cm.__exit__(exc_type, exc_val, exc_tb)
            self._exec.__exit__(exc_type, exc_val, exc_tb)

    def record_step(self, tokens: int = 0, tool_calls: int = 0,
                    depth: int = 0, tag: str | None = None) -> StepOutcome:
        if self._tracer is not None and _OTEL_AVAILABLE:
            with self._tracer.start_as_current_span(
                "iaiso.step",
                attributes={
                    "iaiso.tokens": tokens,
                    "iaiso.tool_calls": tool_calls,
                    "iaiso.depth": depth,
                    "iaiso.tag": tag or "",
                },
            ) as span:
                try:
                    outcome = self._exec.record_step(
                        tokens=tokens, tool_calls=tool_calls, depth=depth, tag=tag,
                    )
                    span.set_attribute("iaiso.outcome", outcome.value)
                    span.set_attribute(
                        "iaiso.pressure_after",
                        self._exec.snapshot().pressure,
                    )
                    return outcome
                except Exception as exc:
                    span.record_exception(exc)
                    span.set_status(Status(StatusCode.ERROR, str(exc)))
                    raise
        return self._exec.record_step(
            tokens=tokens, tool_calls=tool_calls, depth=depth, tag=tag,
        )

    def check(self) -> StepOutcome:
        return self._exec.check()

    def snapshot(self) -> Any:
        return self._exec.snapshot()

    def require_scope(self, scope: str) -> None:
        return self._exec.require_scope(scope)

    @property
    def engine(self) -> Any:
        return self._exec.engine

    def __getattr__(self, name: str) -> Any:
        # Fall through to the underlying execution for anything we don't
        # specifically override.
        return getattr(self._exec, name)


@contextmanager
def step_span(tracer: Any, name: str, **attributes: Any) -> Iterator[Any]:
    """Convenience context manager for a single OTel span around a tool call.

    Typical use: wrapping individual tool invocations inside an agent
    step so they appear as grandchildren in the trace tree.

        with step_span(tracer, "tool.search", query="pandas docs") as span:
            results = search(query)
            span.set_attribute("results.count", len(results))
    """
    if tracer is None or not _OTEL_AVAILABLE:
        yield None
        return
    with tracer.start_as_current_span(name, attributes=attributes) as span:
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            if _OTEL_AVAILABLE:
                span.set_status(Status(StatusCode.ERROR, str(exc)))
            raise
