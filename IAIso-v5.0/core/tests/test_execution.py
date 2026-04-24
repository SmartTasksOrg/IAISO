"""Tests for BoundedExecution (engine + consent + audit together)."""

from __future__ import annotations

import pytest

from iaiso import (
    BoundedExecution,
    ConsentIssuer,
    ConsentVerifier,
    ExecutionLocked,
    InsufficientScope,
    MemorySink,
    PressureConfig,
    ScopeRequired,
    StepOutcome,
    generate_hs256_secret,
)


def test_basic_lifecycle() -> None:
    sink = MemorySink()
    with BoundedExecution.start(audit_sink=sink) as exec_:
        exec_.record_tokens(500)
        exec_.record_tool_call(name="search")
    kinds = [e.kind for e in sink.events]
    assert "engine.init" in kinds
    assert "execution.closed" in kinds


def test_scope_required_without_consent() -> None:
    with BoundedExecution.start() as exec_:
        with pytest.raises(ScopeRequired):
            exec_.require_scope("tools.search")


def test_scope_granted_with_matching_consent() -> None:
    secret = generate_hs256_secret()
    issuer = ConsentIssuer(signing_key=secret)
    verifier = ConsentVerifier(verification_key=secret)

    token = issuer.issue(subject="alice", scopes=["tools"])
    verified = verifier.verify(token.token)

    sink = MemorySink()
    with BoundedExecution.start(consent=verified, audit_sink=sink) as exec_:
        exec_.require_scope("tools.search")
        exec_.require_scope("tools.fetch")

    assert len(sink.by_kind("consent.granted")) == 2


def test_scope_denied_with_insufficient_consent() -> None:
    secret = generate_hs256_secret()
    issuer = ConsentIssuer(signing_key=secret)
    verifier = ConsentVerifier(verification_key=secret)

    token = issuer.issue(subject="alice", scopes=["read"])
    verified = verifier.verify(token.token)

    sink = MemorySink()
    with BoundedExecution.start(consent=verified, audit_sink=sink) as exec_:
        with pytest.raises(InsufficientScope):
            exec_.require_scope("write")

    assert len(sink.by_kind("consent.denied")) == 1


def test_execution_locks_after_release() -> None:
    cfg = PressureConfig(
        escalation_threshold=0.5,
        release_threshold=0.7,
        token_coefficient=1.0,
        dissipation_per_step=0.0,
        post_release_lock=True,
    )
    with BoundedExecution.start(config=cfg) as exec_:
        outcome = exec_.record_tokens(1000)
        assert outcome is StepOutcome.RELEASED
        with pytest.raises(ExecutionLocked):
            exec_.record_tokens(100)


def test_reset_unlocks_execution() -> None:
    cfg = PressureConfig(
        escalation_threshold=0.5,
        release_threshold=0.7,
        token_coefficient=1.0,
        dissipation_per_step=0.0,
        post_release_lock=True,
    )
    with BoundedExecution.start(config=cfg) as exec_:
        exec_.record_tokens(1000)  # releases + locks
        exec_.reset()
        outcome = exec_.record_tokens(100)
        assert outcome is StepOutcome.OK


def test_check_does_not_count_work() -> None:
    with BoundedExecution.start() as exec_:
        exec_.record_tokens(500)
        pressure_before_check = exec_.snapshot().pressure
        exec_.check()
        pressure_after_check = exec_.snapshot().pressure
        assert pressure_before_check == pressure_after_check
