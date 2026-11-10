"""Tests for PressureWrapper, the one-line agent wrapper from the README."""

from __future__ import annotations

import asyncio
import warnings

import pytest

from iaiso import (
    ConsentIssuer,
    ConsentVerifier,
    ExecutionLocked,
    IAIsoPressureWrapper,
    InsufficientScope,
    MemorySink,
    PressureConfig,
    PressureEscalated,
    PressureWrapper,
    ScopeRequired,
    StepOutcome,
    generate_hs256_secret,
)
from iaiso.core.wrapper import extract_usage


class RunAgent:
    """Stands in for a LangChain/CrewAI-style agent with a run() method."""

    def __init__(self, result=None):
        self.calls = []
        self.result = result if result is not None else {"output": "done"}
        self.memory = "agent memory"

    def run(self, task):
        self.calls.append(task)
        return self.result


def _tool_heavy(n):
    return {"output": "ok", "tool_calls": [{"name": f"t{i}"} for i in range(n)]}


def test_readme_quick_start_runs_and_returns_result():
    agent = RunAgent()
    sink = MemorySink()
    safe_agent = PressureWrapper(agent, max_pressure=0.85, audit_sink=sink)
    assert safe_agent.run("Your task here") == {"output": "done"}
    assert agent.calls == ["Your task here"]
    assert sink.by_kind("engine.step")


def test_readme_enable_backprop_warns_and_changes_nothing():
    with pytest.warns(DeprecationWarning, match="enable_backprop has no effect"):
        safe_agent = PressureWrapper(RunAgent(), max_pressure=0.85, enable_backprop=True)
    assert safe_agent.run("x") == {"output": "done"}


def test_thresholds_follow_max_pressure():
    w = PressureWrapper(RunAgent(), max_pressure=0.85)
    cfg = w.execution.engine.config
    assert cfg.release_threshold == 0.85
    assert cfg.escalation_threshold == pytest.approx(0.75)


def test_config_takes_precedence():
    cfg = PressureConfig(escalation_threshold=0.5, release_threshold=0.6)
    w = PressureWrapper(RunAgent(), max_pressure=0.99, config=cfg)
    assert w.execution.engine.config.release_threshold == 0.6


def test_invalid_max_pressure_rejected():
    with pytest.raises(ValueError):
        PressureWrapper(RunAgent(), max_pressure=0)
    with pytest.raises(ValueError):
        PressureWrapper(RunAgent(), max_pressure=0.5, escalate_at=0.6)


def test_method_resolution():
    class InvokeOnly:
        def invoke(self, x):
            return x * 2

    class Crew:
        def kickoff(self, inputs=None):
            return {"crew": inputs}

    assert PressureWrapper(InvokeOnly()).run(3) == 6
    assert PressureWrapper(Crew()).kickoff(inputs={"a": 1}) == {"crew": {"a": 1}}
    assert PressureWrapper(lambda t: t.upper())("hi") == "HI"
    with pytest.raises(TypeError, match="cannot find how to call"):
        PressureWrapper(object())
    with pytest.raises(TypeError, match="no callable method"):
        PressureWrapper(RunAgent(), method="missing")


def test_attributes_forward_to_agent():
    w = PressureWrapper(RunAgent())
    assert w.memory == "agent memory"


@pytest.mark.parametrize("result,expected", [
    ({"usage": {"total_tokens": 1200}}, (1200, 0)),
    ({"usage": {"input_tokens": 100, "output_tokens": 50}}, (150, 0)),          # Anthropic
    ({"usage": {"prompt_tokens": 30, "completion_tokens": 20}}, (50, 0)),       # OpenAI
    ({"usage_metadata": {"total_tokens": 77}, "tool_calls": [1, 2]}, (77, 2)),  # LangChain message
    ({"output": "x", "intermediate_steps": [("a", "b")] * 3}, (0, 3)),          # LangChain agent
    ({"llm_output": {"token_usage": {"total_tokens": 9}}}, (9, 0)),             # LLMResult
    ("plain string", (0, 0)),
])
def test_extract_usage(result, expected):
    assert extract_usage(result) == expected


def test_extract_usage_from_objects():
    class Usage:
        input_tokens = 10
        output_tokens = 5

    class Message:
        usage = Usage()
        tool_calls = [object()]

    assert extract_usage(Message()) == (15, 1)


def test_tokens_estimated_when_not_reported():
    sink = MemorySink()
    w = PressureWrapper(lambda t: "y" * 400, audit_sink=sink)
    w.run("x" * 400)
    step = sink.by_kind("engine.step")[-1]
    assert step.data["tokens"] == 200
    assert step.data["tag"] == "agent.call.estimated"


def test_token_counter_used_before_estimate():
    sink = MemorySink()
    w = PressureWrapper(lambda t: "r", audit_sink=sink, token_counter=lambda task, res: 42)
    w.run("t")
    assert sink.by_kind("engine.step")[-1].data["tokens"] == 42


def test_escalation_pauses_next_call_until_approved():
    cfg = PressureConfig(escalation_threshold=0.2, release_threshold=0.9,
                         tool_coefficient=0.1, dissipation_per_step=0.0)
    agent = RunAgent(_tool_heavy(3))
    w = PressureWrapper(agent, config=cfg)
    w.run("first")                        # 0.3 > 0.2: escalated after this call
    assert w.last_outcome is StepOutcome.ESCALATED
    with pytest.raises(PressureEscalated) as exc:
        w.run("second")
    assert exc.value.snapshot.pressure == pytest.approx(0.3, abs=0.01)  # plus estimated tokens
    assert agent.calls == ["first"]       # the agent was not called
    w.approve()
    w.run("second")                       # one approved call goes through
    with pytest.raises(PressureEscalated):
        w.run("third")                    # approval covers one call only


def test_escalation_continue_and_handler():
    cfg = PressureConfig(escalation_threshold=0.2, release_threshold=0.99,
                         tool_coefficient=0.1, dissipation_per_step=0.0)
    w = PressureWrapper(RunAgent(_tool_heavy(3)), config=cfg, on_escalation="continue")
    w.run("a"); w.run("b")                # continues while escalated

    seen = []
    def handler(wrapper, snap):
        seen.append(snap.pressure)
        return False
    w2 = PressureWrapper(RunAgent(_tool_heavy(3)), config=cfg, on_escalation=handler)
    w2.run("a")
    with pytest.raises(PressureEscalated, match="handler refused"):
        w2.run("b")
    assert seen

    with pytest.raises(ValueError):
        PressureWrapper(RunAgent(), on_escalation="ignore")


def test_release_locks_until_reset():
    cfg = PressureConfig(escalation_threshold=0.2, release_threshold=0.3,
                         tool_coefficient=0.2, dissipation_per_step=0.0)
    agent = RunAgent(_tool_heavy(2))
    w = PressureWrapper(agent, config=cfg)
    result = w.run("big")                 # 0.4 >= 0.3: released, then locked
    assert result == agent.result         # the finished work is still returned
    assert w.last_outcome is StepOutcome.RELEASED
    with pytest.raises(ExecutionLocked):
        w.run("next")
    assert len(agent.calls) == 1
    w.reset()
    w.run("after reset")
    assert len(agent.calls) == 2


def test_budget_lock_returns_result_then_refuses():
    cfg = PressureConfig(budget_usd=0.001, model_costs={"m": 1000.0})
    agent = RunAgent({"usage": {"total_tokens": 10}})
    w = PressureWrapper(agent, config=cfg, model="m")
    assert w.run("spend") == agent.result
    assert w.last_outcome is StepOutcome.LOCKED
    with pytest.raises(ExecutionLocked):
        w.run("more")


def test_required_scope_enforced():
    with pytest.raises(ScopeRequired):
        PressureWrapper(RunAgent(), required_scope="tools.search").run("x")

    secret = generate_hs256_secret()
    issuer = ConsentIssuer.v1(signing_key=secret)
    verifier = ConsentVerifier.v1(verification_key=secret)
    granted = verifier.verify(issuer.issue(subject="alice", scopes=["tools"]).token)
    w = PressureWrapper(RunAgent(), consent=granted, required_scope="tools.search")
    assert w.run("x") == {"output": "done"}

    narrow = verifier.verify(issuer.issue(subject="bob", scopes=["files"]).token)
    with pytest.raises(InsufficientScope):
        PressureWrapper(RunAgent(), consent=narrow, required_scope="tools.search").run("x")


def test_tools_can_report_themselves():
    sink = MemorySink()
    w = PressureWrapper(RunAgent(), audit_sink=sink)
    w.record_tool_call("search")
    assert sink.by_kind("engine.step")[-1].data["tool_calls"] == 1


def test_context_manager_closes_execution():
    sink = MemorySink()
    with PressureWrapper(RunAgent(), audit_sink=sink) as w:
        w.run("x")
    assert sink.by_kind("execution.closed")


def test_async_agents():
    class AsyncAgent:
        def run(self, t):
            return "sync"

        async def ainvoke(self, t):
            return {"output": t, "usage": {"total_tokens": 5}}

    w = PressureWrapper(AsyncAgent())
    out = asyncio.run(w.arun("go"))
    assert out == {"output": "go", "usage": {"total_tokens": 5}}


def test_spec_alias_arguments():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        w = IAIsoPressureWrapper(RunAgent(), pressure_threshold=0.85,
                                 enable_magnification=True)
    assert w.execution.engine.config.release_threshold == 0.85
    with pytest.raises(ScopeRequired):
        IAIsoPressureWrapper(RunAgent(), consent_scope="gov.enterprise.finance.v1").run("x")


def test_strict_mode_refuses_degraded_setup():
    from iaiso import StrictModeError
    with pytest.raises(StrictModeError):
        PressureWrapper(RunAgent(), enforcement_mode="strict")


def test_readme_quick_start_snippet_runs(tmp_path, monkeypatch):
    """Run the README's Option 1 code block, so the README cannot drift again."""
    import pathlib
    import re

    readme = pathlib.Path(__file__).resolve().parents[4] / "README.md"
    if not readme.exists():
        pytest.skip("README.md is not shipped with this package")
    text = readme.read_text(encoding="utf-8")
    section = text.split("### Option 1", 1)[1]
    code = re.search(r"```python\n(.*?)```", section, re.S).group(1)
    monkeypatch.chdir(tmp_path)
    namespace = {"your_agent": RunAgent()}
    exec(compile(code, "README.md", "exec"), namespace)
    assert namespace["your_agent"].calls == ["Your task here"]
    assert (tmp_path / "audit.jsonl").exists()
