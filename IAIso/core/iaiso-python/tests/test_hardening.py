"""Regression tests for the hardening found in the November 2026 devil's-advocate review.

Each test names the bypass it closes. Defaults that the 1.0 conformance vectors
pin are unchanged; the new protections are either input validation (no valid
input changes behaviour) or opt-in configuration.
"""
import pytest

from iaiso import (ConsentIssuer, ConsentVerifier, InvalidToken, PressureConfig, PressureEngine,
                   StepInput, generate_hs256_secret)
from iaiso.core.engine import Lifecycle


def engine(**kw):
    return PressureEngine(PressureConfig(**kw), execution_id="t", clock=lambda: 0.0)


@pytest.mark.parametrize("field", ["tokens", "tool_calls", "depth"])
@pytest.mark.parametrize("bad", [-1, -40000, 1.5, float("nan"), float("inf"), True, "10", None])
def test_step_input_rejects_values_that_lower_or_poison_pressure(field, bad):
    with pytest.raises(ValueError):
        StepInput(**{field: bad})


def test_empty_steps_cannot_drain_pressure_when_disabled():
    e = engine(empty_step_dissipation=False)
    e.step(StepInput(tokens=50_000))
    before = e.pressure
    for _ in range(40):
        e.step(StepInput())
    assert e.pressure == pytest.approx(before)


def test_empty_steps_still_dissipate_under_v1():  # 1.x behaviour, opt-in
    e = PressureEngine(PressureConfig.v1(), execution_id="t", clock=lambda: 0.0)
    e.step(StepInput(tokens=50_000))
    before = e.pressure
    e.step(StepInput())
    assert e.pressure < before


def test_unpriced_model_is_charged_when_fail_closed():
    e = engine(model_costs={"gpt-4o": 10.0}, unpriced_model_usd_per_million=100.0, budget_usd=1.0,
               token_coefficient=0.0)
    e.step(StepInput(tokens=5_000, model="gpt-4o-2024-08-06"))       # renamed model: not free
    assert e.spend_usd == pytest.approx(0.5)
    assert e.step(StepInput(tokens=6_000, model=None)).value == "locked"  # no model: not free


def test_unpriced_model_is_free_under_v1():  # 1.x behaviour, opt-in
    e = PressureEngine(PressureConfig.v1(model_costs={"gpt-4o": 10.0}), execution_id="t",
                       clock=lambda: 0.0)
    e.step(StepInput(tokens=1_000_000, model="other"))
    assert e.spend_usd == 0.0


def test_price_lets_callers_refuse_before_doing_the_work():
    e = engine(model_costs={"m": 10.0}, budget_usd=1.0, token_coefficient=0.0)
    w = StepInput(tokens=50_000_000, model="m")
    assert e.price(w) == pytest.approx(500.0)
    assert e.budget_remaining_usd == pytest.approx(1.0)
    assert e.spend_usd + e.price(w) > 1.0      # the caller can refuse here; nothing was spent


def test_reset_can_unlock_without_refilling_budget():
    e = engine(model_costs={"m": 10.0}, budget_usd=1.0, token_coefficient=0.0)
    e.step(StepInput(tokens=200_000, model="m"))
    assert e.lifecycle is Lifecycle.LOCKED
    e.reset(clear_spend=False, by="reviewer@corp")
    assert e.spend_usd == pytest.approx(2.0)
    assert e.step(StepInput(tokens=1, model="m")).value == "locked"


def test_bad_config_values_are_refused():
    with pytest.raises(ValueError):
        PressureConfig(unpriced_model_usd_per_million=-1.0)
    with pytest.raises(ValueError):
        PressureConfig(unpriced_model_usd_per_million=float("nan"))


KEY = generate_hs256_secret()


def test_audience_stops_cross_service_replay():
    tok = ConsentIssuer(signing_key=KEY, algorithm="HS256", audience="payments").issue(
        "alice", ["tools.pay"]).token
    v = lambda aud: ConsentVerifier(verification_key=KEY, algorithm="HS256", audience=aud)
    assert v("payments").verify(tok).subject == "alice"
    with pytest.raises(InvalidToken):
        v("search").verify(tok)
    with pytest.raises(InvalidToken):
        ConsentVerifier.v1(verification_key=KEY).verify(tok)


def test_execution_binding_is_required_by_default():  # 2.0
    tok = ConsentIssuer(signing_key=KEY, algorithm="HS256", audience="a").issue(
        "alice", ["tools.pay"]).token
    with pytest.raises(InvalidToken):
        ConsentVerifier(verification_key=KEY, algorithm="HS256", audience="a").verify(
            tok, execution_id="prod-1")
    assert ConsentVerifier(verification_key=KEY, algorithm="HS256", audience="a",
                           require_execution_binding=False).verify(
        tok, execution_id="prod-1").subject == "alice"


@pytest.mark.parametrize("key", ["a", "short-secret", b"x" * 31])
def test_short_hs256_keys_are_refused(key):
    with pytest.raises(ValueError, match="at least 32"):
        ConsentIssuer(signing_key=key, algorithm="HS256", audience="a")
    with pytest.raises(ValueError, match="at least 32"):
        ConsentVerifier(verification_key=key, algorithm="HS256", audience="a")


def test_non_positive_ttl_is_refused():
    with pytest.raises(ValueError):
        ConsentIssuer.v1(signing_key=KEY).issue("alice", ["x"], ttl_seconds=0)
