"""Tests for the evaluation harness."""

from __future__ import annotations

from pathlib import Path

from iaiso.evaluation import (
    DEFAULT_SCENARIOS,
    IAIsoGuard,
    NoLimitGuard,
    TokenBudgetGuard,
    ToolCallCounterGuard,
    WorkItem,
    Scenario,
    default_guards,
    run_scenario,
    run_suite,
)


def test_no_limit_guard_allows_everything() -> None:
    guard = NoLimitGuard()
    scenario = Scenario(
        name="test",
        description="x",
        items=tuple(WorkItem(tokens=100) for _ in range(5)),
        expected_outcome="bounded",
    )
    result = run_scenario(scenario, guard)
    assert result.allowed_steps == 5
    assert result.rejected_steps == 0


def test_token_budget_exhausts() -> None:
    guard = TokenBudgetGuard(budget=250)
    scenario = Scenario(
        name="test",
        description="x",
        items=tuple(WorkItem(tokens=100) for _ in range(5)),
        expected_outcome="runaway",
    )
    result = run_scenario(scenario, guard)
    # 100+100 allowed, third would put us at 300 > 250, so rejected.
    # From that point all are rejected.
    assert result.allowed_steps == 2
    assert result.rejected_steps == 3
    assert result.ended_in_state == "exhausted"


def test_tool_counter_exhausts() -> None:
    guard = ToolCallCounterGuard(max_calls=3)
    scenario = Scenario(
        name="test",
        description="x",
        items=tuple(WorkItem(tool_calls=1) for _ in range(5)),
        expected_outcome="runaway",
    )
    result = run_scenario(scenario, guard)
    assert result.allowed_steps == 3
    assert result.rejected_steps == 2


def test_iaiso_guard_escalates_on_runaway() -> None:
    guard = IAIsoGuard()
    scenario = Scenario(
        name="test",
        description="x",
        items=tuple(WorkItem(tool_calls=5) for _ in range(20)),
        expected_outcome="runaway",
    )
    result = run_scenario(scenario, guard)
    assert result.escalated_steps >= 1


def test_run_suite_writes_outputs(tmp_path: Path) -> None:
    results = run_suite(output_dir=tmp_path)
    assert (tmp_path / "summary.csv").exists()
    assert (tmp_path / "steps.jsonl").exists()
    # 6 default scenarios x 4 default guards = 24 rows
    assert len(results) == len(DEFAULT_SCENARIOS) * len(default_guards())
