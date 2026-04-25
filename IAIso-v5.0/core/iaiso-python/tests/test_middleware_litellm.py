"""Tests for the LiteLLM middleware.

Uses a stub `litellm` module injected into `sys.modules` so we test the
wrapper logic without pulling in the real LiteLLM package (which has a
heavy dependency footprint). The stub produces OpenAI-shaped responses,
which is what LiteLLM itself produces — so the wrapper's accounting
logic is exercised identically to a real LiteLLM call.
"""

from __future__ import annotations

import asyncio
import sys
import types
from typing import Any

import pytest

from iaiso import BoundedExecution, MemorySink, PressureConfig
from iaiso.core import ExecutionLocked


class _FakeUsage:
    def __init__(self, total: int) -> None:
        self.total_tokens = total
        self.prompt_tokens = total // 2
        self.completion_tokens = total - (total // 2)


class _FakeToolCall:
    def __init__(self, name: str) -> None:
        self.function = types.SimpleNamespace(name=name, arguments="{}")


class _FakeMessage:
    def __init__(self, tool_calls: list[_FakeToolCall] | None = None) -> None:
        self.tool_calls = tool_calls or []
        self.content = "ok"


class _FakeChoice:
    def __init__(self, message: _FakeMessage) -> None:
        self.message = message


class _FakeResponse:
    def __init__(
        self,
        model: str,
        tokens: int,
        tool_calls: list[str] | None = None,
    ) -> None:
        self.model = model
        self.usage = _FakeUsage(tokens)
        self.choices = [
            _FakeChoice(_FakeMessage([_FakeToolCall(n) for n in (tool_calls or [])]))
        ]


@pytest.fixture
def fake_litellm(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    """Install a stub `litellm` module that mimics the real API surface."""
    mod = types.ModuleType("litellm")
    call_log: list[dict[str, Any]] = []

    def completion(**kwargs: Any) -> _FakeResponse:
        call_log.append({"sync": True, **kwargs})
        return _FakeResponse(
            model=kwargs.get("model", "unknown"),
            tokens=kwargs.get("_fake_tokens", 100),
            tool_calls=kwargs.get("_fake_tool_calls"),
        )

    async def acompletion(**kwargs: Any) -> _FakeResponse:
        call_log.append({"sync": False, **kwargs})
        return _FakeResponse(
            model=kwargs.get("model", "unknown"),
            tokens=kwargs.get("_fake_tokens", 100),
            tool_calls=kwargs.get("_fake_tool_calls"),
        )

    mod.completion = completion  # type: ignore[attr-defined]
    mod.acompletion = acompletion  # type: ignore[attr-defined]
    mod.call_log = call_log  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "litellm", mod)
    return mod


def test_completion_accounts_tokens(fake_litellm: types.ModuleType) -> None:
    from iaiso.middleware.litellm import BoundedLiteLLM

    sink = MemorySink()
    with BoundedExecution.start(
        # Disable dissipation so we can cleanly observe the contribution.
        config=PressureConfig(token_coefficient=0.1, dissipation_per_step=0.0),
        audit_sink=sink,
    ) as exec_:
        llm = BoundedLiteLLM(exec_)
        resp = llm.completion(
            model="gpt-4o",
            messages=[{"role": "user", "content": "hi"}],
            _fake_tokens=5000,
        )
        assert resp.usage.total_tokens == 5000
        # 5000 tokens × (0.1 per 1000) = 0.5
        assert exec_.snapshot().pressure == pytest.approx(0.5, abs=0.01)


def test_completion_accounts_tool_calls(fake_litellm: types.ModuleType) -> None:
    from iaiso.middleware.litellm import BoundedLiteLLM

    with BoundedExecution.start(
        config=PressureConfig(
            tool_coefficient=0.1,
            token_coefficient=0.0,
            dissipation_per_step=0.0,
        ),
    ) as exec_:
        llm = BoundedLiteLLM(exec_)
        llm.completion(
            model="gpt-4o",
            messages=[{"role": "user", "content": "hi"}],
            _fake_tokens=0,
            _fake_tool_calls=["search", "calculator"],
        )
        # Two tool calls × 0.1 = 0.2 pressure
        assert exec_.snapshot().pressure == pytest.approx(0.2, abs=0.01)


def test_completion_records_audit_tag(fake_litellm: types.ModuleType) -> None:
    from iaiso.middleware.litellm import BoundedLiteLLM

    sink = MemorySink()
    with BoundedExecution.start(audit_sink=sink) as exec_:
        llm = BoundedLiteLLM(exec_)
        llm.completion(model="ollama/llama3", messages=[])

    step_events = [e for e in sink.events if e.kind == "engine.step"]
    assert step_events
    assert any("litellm.completion:ollama/llama3" in str(e.data.get("tag", ""))
               for e in step_events)


def test_locked_execution_blocks_call(fake_litellm: types.ModuleType) -> None:
    from iaiso.middleware.litellm import BoundedLiteLLM

    # Force immediate lock: 50k tokens × (0.5 per 1000) = 25.0 → clamped to 1.0
    cfg = PressureConfig(
        token_coefficient=0.5,
        dissipation_per_step=0.0,
        escalation_threshold=0.1,
        release_threshold=0.2,
    )
    with BoundedExecution.start(config=cfg) as exec_:
        llm = BoundedLiteLLM(exec_)
        llm.completion(model="gpt-4o", messages=[], _fake_tokens=50_000)
        # Second call should refuse — execution locked after release threshold
        with pytest.raises(ExecutionLocked):
            llm.completion(model="gpt-4o", messages=[], _fake_tokens=10)


def test_escalation_raises_when_configured(fake_litellm: types.ModuleType) -> None:
    from iaiso.middleware.litellm import BoundedLiteLLM, EscalationRaised

    # 3000 tokens × (0.1 per 1000) = 0.3 → escalated but not released
    cfg = PressureConfig(
        token_coefficient=0.1,
        dissipation_per_step=0.0,
        escalation_threshold=0.2,
        release_threshold=0.99,
    )
    with BoundedExecution.start(config=cfg) as exec_:
        llm = BoundedLiteLLM(exec_, raise_on_escalation=True)
        llm.completion(model="gpt-4o", messages=[], _fake_tokens=3000)
        # Next call should raise because we're escalated
        with pytest.raises(EscalationRaised):
            llm.completion(model="gpt-4o", messages=[], _fake_tokens=10)


def test_async_completion(fake_litellm: types.ModuleType) -> None:
    from iaiso.middleware.litellm import BoundedLiteLLM

    async def run() -> None:
        with BoundedExecution.start(
            config=PressureConfig(
                token_coefficient=0.1,
                dissipation_per_step=0.0,
            ),
        ) as exec_:
            llm = BoundedLiteLLM(exec_)
            resp = await llm.acompletion(
                model="anthropic/claude-opus-4-7",
                messages=[{"role": "user", "content": "hi"}],
                _fake_tokens=3000,
            )
            assert resp.usage.total_tokens == 3000
            # 3000 × (0.1 per 1000) = 0.3
            assert exec_.snapshot().pressure == pytest.approx(0.3, abs=0.01)

    asyncio.run(run())


def test_missing_usage_defaults_to_zero(fake_litellm: types.ModuleType) -> None:
    """Streaming-style responses may arrive without a usage field. The wrapper
    must still record a step, just with tokens=0."""
    from iaiso.middleware.litellm import BoundedLiteLLM

    # Replace the stub's completion with one that returns a response
    # without `usage`.
    def completion_no_usage(**kwargs: Any) -> types.SimpleNamespace:
        return types.SimpleNamespace(
            model=kwargs["model"],
            usage=None,
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(
                tool_calls=[], content=""
            ))],
        )
    fake_litellm.completion = completion_no_usage  # type: ignore[attr-defined]

    sink = MemorySink()
    with BoundedExecution.start(audit_sink=sink) as exec_:
        llm = BoundedLiteLLM(exec_)
        llm.completion(model="gpt-4o", messages=[])
    step_events = [e for e in sink.events if e.kind == "engine.step"]
    assert step_events
    assert step_events[0].data.get("tokens") == 0


def test_router_wrapper_accounts_calls(fake_litellm: types.ModuleType) -> None:
    from iaiso.middleware.litellm import BoundedLiteLLMRouter

    class FakeRouter:
        def completion(self, **kwargs: Any) -> _FakeResponse:
            return _FakeResponse(model=kwargs["model"], tokens=4000)

        def get_model_list(self) -> list[str]:
            return ["gpt-4o", "claude-opus-4-7"]

    sink = MemorySink()
    with BoundedExecution.start(
        config=PressureConfig(
            token_coefficient=0.1,
            dissipation_per_step=0.0,
        ),
        audit_sink=sink,
    ) as exec_:
        router = FakeRouter()
        bounded = BoundedLiteLLMRouter(router, exec_)
        resp = bounded.completion(model="gpt-4o", messages=[])
        assert resp.usage.total_tokens == 4000
        # 4000 × (0.1 per 1000) = 0.4
        assert exec_.snapshot().pressure == pytest.approx(0.4, abs=0.01)
        # Pass-through works
        assert bounded.get_model_list() == ["gpt-4o", "claude-opus-4-7"]
