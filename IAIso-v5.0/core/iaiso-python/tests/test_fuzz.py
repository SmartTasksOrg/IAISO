"""Property-based fuzzing of the engine, reservations, consent and proxy
parsing. Each property is an invariant an attacker would need to break.

Run more examples locally:  HYPOTHESIS_PROFILE=deep pytest tests/test_fuzz.py
"""

from __future__ import annotations

import math
import os

import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from iaiso import (
    ConsentIssuer,
    ConsentVerifier,
    InvalidToken,
    PressureConfig,
    PressureEngine,
    StepInput,
    generate_ed25519_keypair,
)
from iaiso.consent import ConsentError
from iaiso.core.engine import Lifecycle, ReservationRefused, StepOutcome
from iaiso.proxy import EnforcementProxy

settings.register_profile("ci", max_examples=200, deadline=None,
                          suppress_health_check=[HealthCheck.too_slow])
settings.register_profile("deep", max_examples=5000, deadline=None,
                          suppress_health_check=[HealthCheck.too_slow])
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "ci"))

counts = st.integers(min_value=0, max_value=2**53)
work = st.builds(StepInput, tokens=counts, tool_calls=st.integers(0, 1000),
                 depth=st.integers(0, 100))
bad_values = st.one_of(
    st.integers(max_value=-1), st.floats(allow_nan=True, allow_infinity=True),
    st.booleans(), st.text(), st.none(), st.lists(st.integers(), max_size=2),
)


def make(cfg: PressureConfig | None = None) -> PressureEngine:
    return PressureEngine(cfg or PressureConfig(), execution_id="fuzz", clock=lambda: 0.0)


@given(field=st.sampled_from(["tokens", "tool_calls", "depth"]), value=bad_values)
def test_step_input_never_accepts_a_non_count(field, value):
    if isinstance(value, float) and value.is_integer() and value >= 0:
        value = -1.0  # keep the property about non-counts
    with pytest.raises(ValueError):
        StepInput(**{field: value})


@given(steps=st.lists(work, max_size=40))
def test_pressure_is_always_finite_and_in_unit_interval(steps):
    e = make()
    for w in steps:
        e.step(w)
        assert math.isfinite(e.pressure) and 0.0 <= e.pressure <= 1.0


@given(steps=st.lists(work, min_size=1, max_size=40))
def test_empty_steps_never_lower_pressure(steps):
    e = make()
    for w in steps:
        e.step(w)
    if e.lifecycle is Lifecycle.LOCKED:
        return
    before = e.pressure
    for _ in range(10):
        e.step(StepInput())
    assert e.pressure == before


@given(cap=st.integers(1, 10_000), steps=st.lists(work, max_size=60))
def test_lifetime_token_cap_is_never_exceeded_by_more_than_one_step(cap, steps):
    e = make(PressureConfig(max_total_tokens=cap, post_release_lock=False))
    largest = 0
    for w in steps:
        before = e.totals["tokens"]
        out = e.step(w)
        if out is not StepOutcome.LOCKED or e.totals["tokens"] != before:
            largest = max(largest, w.tokens)
    # The step that crosses the cap is accounted (the work already happened);
    # nothing after it is.
    assert e.totals["tokens"] < cap + max(largest, 1)
    if e.totals["tokens"] >= cap:
        assert e.lifecycle is Lifecycle.LOCKED


@given(cap=st.integers(1, 5_000), asks=st.lists(st.integers(0, 2_000), max_size=60))
def test_reservations_never_exceed_cap(cap, asks):
    e = make(PressureConfig(max_total_tokens=cap, token_coefficient=0.0))
    held = []
    for n in asks:
        try:
            held.append(e.reserve(StepInput(tokens=n)))
        except ReservationRefused:
            pass
        assert sum(r.tokens for r in held) + e.totals["tokens"] <= cap
    for r in held:
        e.commit(r, StepInput(tokens=r.tokens))
    assert e.totals["tokens"] <= cap


@given(price=st.floats(0.01, 100), budget=st.floats(0.01, 50),
       asks=st.lists(st.integers(1, 2_000_000), max_size=30))
def test_reservations_never_exceed_budget(price, budget, asks):
    e = make(PressureConfig(model_costs={"m": price}, budget_usd=budget, token_coefficient=0.0))
    for n in asks:
        try:
            r = e.reserve(StepInput(tokens=n, model="m"))
        except ReservationRefused:
            continue
        e.commit(r, StepInput(tokens=n, model="m"))
    assert e.spend_usd <= budget + 1e-9


@given(model=st.text(max_size=20), tokens=st.integers(1, 10**7))
def test_unknown_models_are_never_cheaper_than_the_cheapest_known(model, tokens):
    costs = {"a": 1.0, "b": 30.0}
    e = make(PressureConfig(model_costs=costs))
    charged = e.price(StepInput(tokens=tokens, model=model))
    assert charged >= tokens / 1e6 * min(costs.values()) - 1e-12


KEYS = generate_ed25519_keypair()
ISS = ConsentIssuer(signing_key=KEYS[0], audience="fuzz")
VER = ConsentVerifier(verification_key=KEYS[1], audience="fuzz")
GOOD = ISS.issue("s", ["x"], execution_id="e").token


@given(junk=st.text(max_size=400))
def test_verifier_only_raises_consent_errors_on_garbage(junk):
    try:
        VER.verify(junk, execution_id="e")
    except ConsentError:
        return
    assert junk == GOOD


@given(pos=st.integers(0, len(GOOD) - 1), ch=st.characters(codec="ascii"))
@settings(max_examples=300)
def test_any_single_character_change_breaks_the_token(pos, ch):
    if GOOD[pos] == ch:
        return
    tampered = GOOD[:pos] + ch + GOOD[pos + 1:]
    try:
        VER.verify(tampered, execution_id="e")
    except (InvalidToken, ConsentError):
        return
    # base64url can encode the same bytes two ways only in trailing bits
    assert pos == len(GOOD) - 1


PROVIDER_KEYS = st.one_of(st.sampled_from([
    "usage", "choices", "message", "tool_calls", "content", "type", "output",
    "input_tokens", "output_tokens", "prompt_tokens", "completion_tokens", "total_tokens",
    "cache_read_input_tokens", "tool_use", "function_call"]), st.text(max_size=6))


JSONISH = st.recursive(
    st.one_of(st.none(), st.booleans(), st.integers(), st.floats(allow_nan=False), st.text()),
    lambda c: st.one_of(st.lists(c, max_size=4), st.dictionaries(PROVIDER_KEYS, c, max_size=5)),
    max_leaves=20)


@settings(max_examples=1000)
@given(body=st.dictionaries(PROVIDER_KEYS, JSONISH, max_size=5),
       usage=st.dictionaries(PROVIDER_KEYS, JSONISH, max_size=5))
def test_proxy_usage_parser_never_crashes_or_goes_negative(body, usage):
    body = {**body, "usage": usage}  # always reach the tool-call parsing
    for provider in ("openai", "anthropic"):
        try:
            got = EnforcementProxy.usage_of(provider, body)
        except (TypeError, AttributeError):
            pytest.fail("usage parser crashed on provider JSON")
        if got is not None:
            assert type(got[0]) is int and type(got[1]) is int
            assert got[0] >= 0 and got[1] >= 0


def test_usage_parser_regressions_found_by_probing():
    P = EnforcementProxy
    assert P.usage_of("anthropic", {"usage": {"input_tokens": 5}, "content": 5}) == (5, 0)
    assert P.usage_of("openai", {"usage": {"total_tokens": True}}) == (0, 0)
    assert P.usage_of("openai", {"usage": {"prompt_tokens": 1},
                                 "choices": ["x", {"message": "y"}, {"message": {"tool_calls": 3}}]}) == (1, 0)
