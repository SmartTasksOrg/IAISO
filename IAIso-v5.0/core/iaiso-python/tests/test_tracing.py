"""Tests for OpenTelemetry tracing integration."""

from __future__ import annotations

import pytest

from iaiso import PressureConfig
from iaiso.core import StepOutcome


def test_traced_execution_works_without_tracer() -> None:
    """If no tracer is passed, TracedBoundedExecution should behave like
    a plain BoundedExecution — no imports, no errors."""
    from iaiso.observability.tracing import TracedBoundedExecution

    with TracedBoundedExecution.start(config=PressureConfig()) as exec_:
        outcome = exec_.record_step(tokens=100)
        assert outcome in (StepOutcome.OK, StepOutcome.ESCALATED,
                           StepOutcome.RELEASED)


def test_traced_execution_with_in_memory_tracer() -> None:
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            SimpleSpanProcessor,
        )
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
            InMemorySpanExporter,
        )
    except ImportError:
        pytest.skip("opentelemetry-sdk not installed")

    from iaiso.observability.tracing import TracedBoundedExecution

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test")

    with TracedBoundedExecution.start(
        tracer=tracer,
        config=PressureConfig(token_coefficient=0.01,
                              dissipation_per_step=0.0),
    ) as exec_:
        exec_.record_step(tokens=500)
        exec_.record_step(tokens=200)

    spans = exporter.get_finished_spans()
    span_names = [s.name for s in spans]
    # We expect 2 step spans nested under 1 execution span
    assert span_names.count("iaiso.step") == 2
    assert span_names.count("iaiso.execution") == 1

    # Step spans should carry iaiso.* attributes
    step_spans = [s for s in spans if s.name == "iaiso.step"]
    first = step_spans[0]
    assert first.attributes.get("iaiso.tokens") == 500
    assert "iaiso.outcome" in first.attributes


def test_traced_execution_records_exceptions() -> None:
    try:
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
            InMemorySpanExporter,
        )
        from opentelemetry.trace import StatusCode
    except ImportError:
        pytest.skip("opentelemetry-sdk not installed")

    from iaiso.observability.tracing import TracedBoundedExecution

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test")

    class Boom(RuntimeError):
        pass

    with pytest.raises(Boom):
        with TracedBoundedExecution.start(
            tracer=tracer,
            config=PressureConfig(),
        ):
            raise Boom("nope")

    exec_spans = [s for s in exporter.get_finished_spans()
                  if s.name == "iaiso.execution"]
    assert len(exec_spans) == 1
    assert exec_spans[0].status.status_code == StatusCode.ERROR


def test_step_span_context_manager() -> None:
    try:
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
            InMemorySpanExporter,
        )
    except ImportError:
        pytest.skip("opentelemetry-sdk not installed")

    from iaiso.observability.tracing import step_span

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test")

    with step_span(tracer, "tool.search", query="pandas docs") as span:
        span.set_attribute("results.count", 42)

    spans = exporter.get_finished_spans()
    tool_spans = [s for s in spans if s.name == "tool.search"]
    assert len(tool_spans) == 1
    assert tool_spans[0].attributes.get("query") == "pandas docs"
    assert tool_spans[0].attributes.get("results.count") == 42


def test_step_span_without_tracer_is_noop() -> None:
    from iaiso.observability.tracing import step_span

    # Should not raise even with no tracer
    with step_span(None, "foo") as span:
        assert span is None
