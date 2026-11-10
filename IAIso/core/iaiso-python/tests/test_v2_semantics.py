"""IAIso 2.0 semantics: lifetime caps, reserve/commit, safe defaults, consent
binding, and agent rebuild on release. Each test names the finding it closes
(IDs from iaiso-assurance/findings.yaml)."""

from __future__ import annotations

import threading

import pytest

from iaiso import (
    ConsentIssuer,
    ConsentVerifier,
    InvalidToken,
    PressureConfig,
    PressureEngine,
    StepInput,
    generate_ed25519_keypair,
    generate_hs256_secret,
)
from iaiso.audit import MemorySink
from iaiso.core.engine import (
    ENFORCEMENT_STRICT,
    Lifecycle,
    ReservationRefused,
    StepOutcome,
    StrictModeError,
)
from iaiso.core.wrapper import PressureWrapper


def eng(**kw):
    sink = MemorySink()
    return PressureEngine(PressureConfig(**kw), execution_id="t", audit_sink=sink,
                          clock=lambda: 0.0), sink


# --- I-04 lifetime caps: slow work under the thresholds is bounded ---------

def test_slow_drip_is_stopped_by_max_total_tokens():
    # 900 tokens/step at 0.015/1k adds 0.0135 and decays 0.02: pressure never
    # rises, so 1.x let this run forever. The lifetime cap stops it.
    e, sink = eng(max_total_tokens=9_000)
    outcomes = [e.step(StepInput(tokens=900)) for _ in range(20)]
    assert e.pressure == 0.0
    assert outcomes.index(StepOutcome.LOCKED) == 9
    assert all(o is StepOutcome.LOCKED for o in outcomes[9:])
    assert e.totals["tokens"] == 9_000
    assert sink.by_kind("engine.locked")[0].data["cap"] == "tokens"


@pytest.mark.parametrize("cap,work", [
    ({"max_total_tool_calls": 3}, StepInput(tool_calls=1)),
    ({"max_total_steps": 3}, StepInput(tokens=1)),
])
def test_other_caps(cap, work):
    e, _ = eng(dissipation_per_step=1.0, **cap)
    assert [e.step(work) for _ in range(4)][-2:] == [StepOutcome.LOCKED] * 2


def test_release_does_not_refill_lifetime_caps():
    e, _ = eng(tool_coefficient=0.5, post_release_lock=False, max_total_tool_calls=4)
    assert e.step(StepInput(tool_calls=2)) is StepOutcome.RELEASED
    assert e.totals["tool_calls"] == 2
    assert e.step(StepInput(tool_calls=2)) is StepOutcome.LOCKED  # 2+2 hits the cap


def test_reset_keeping_spend_keeps_caps_exhausted():
    e, _ = eng(max_total_tokens=100)
    e.step(StepInput(tokens=100))
    assert e.lifecycle is Lifecycle.LOCKED
    e.reset(clear_spend=False, by="oncall")
    assert e.step(StepInput(tokens=1)) is StepOutcome.LOCKED
    assert e.totals["tokens"] == 100  # the refused step was not done or counted
    e.reset(by="manager")
    assert e.step(StepInput(tokens=1)) is StepOutcome.OK


def test_strict_mode_requires_a_lifetime_cap():
    with pytest.raises(StrictModeError, match="lifetime cap"):
        PressureEngine(PressureConfig(token_coefficient=0.011), execution_id="t",
                       audit_sink=MemorySink(), enforcement_mode=ENFORCEMENT_STRICT)
    PressureEngine(PressureConfig(token_coefficient=0.011, max_total_steps=10),
                   execution_id="t", audit_sink=MemorySink(),
                   enforcement_mode=ENFORCEMENT_STRICT)


def test_strict_refuses_budget_without_prices():
    with pytest.raises(StrictModeError, match="model_costs"):
        PressureEngine(PressureConfig(token_coefficient=0.011, budget_usd=5.0,
                                      max_total_steps=10),
                       execution_id="t", audit_sink=MemorySink(),
                       enforcement_mode=ENFORCEMENT_STRICT)


@pytest.mark.parametrize("bad", [-1, 1.5, True, "10"])
def test_caps_validated(bad):
    with pytest.raises(ValueError):
        PressureConfig(max_total_tokens=bad)


@pytest.mark.parametrize("field", ["token_coefficient", "dissipation_per_step", "budget_usd"])
def test_non_finite_config_refused(field):
    with pytest.raises(ValueError):
        PressureConfig(**{field: float("inf")})
    with pytest.raises(ValueError):
        PressureConfig(**{field: float("nan")})


# --- I-06 reserve / commit: concurrent callers cannot overspend -------------

def test_reserve_refuses_work_that_would_exceed_budget():
    e, sink = eng(model_costs={"m": 10.0}, budget_usd=1.0)
    with pytest.raises(ReservationRefused) as exc:
        e.reserve(StepInput(tokens=200_000, model="m"))  # $2
    assert exc.value.reason == "budget"
    assert e.spend_usd == 0.0
    assert sink.by_kind("engine.reservation.refused")


def test_reservations_count_against_the_allowance_until_settled():
    e, _ = eng(max_total_tokens=1_000)
    r1 = e.reserve(StepInput(tokens=600))
    with pytest.raises(ReservationRefused, match="tokens"):
        e.reserve(StepInput(tokens=600))
    e.cancel(r1)
    r2 = e.reserve(StepInput(tokens=600))
    assert e.commit(r2, StepInput(tokens=550)) is StepOutcome.OK
    assert e.totals["tokens"] == 550
    with pytest.raises(KeyError):
        e.commit(r2, StepInput(tokens=1))  # settled twice


def test_overrun_is_accounted_and_audited():
    e, sink = eng(max_total_tokens=1_000)
    r = e.reserve(StepInput(tokens=100))
    assert e.commit(r, StepInput(tokens=1_000)) is StepOutcome.LOCKED
    assert sink.by_kind("engine.reservation.overrun")


def test_reserve_refused_when_locked():
    e, _ = eng(max_total_steps=1)
    e.step(StepInput(tokens=1))
    with pytest.raises(ReservationRefused) as exc:
        e.reserve(StepInput(tokens=1))
    assert exc.value.reason == "locked"


def test_concurrent_reservations_never_exceed_budget():
    import time as _t
    e, _ = eng(model_costs={"m": 1.0}, budget_usd=1.0, token_coefficient=0.0)
    real_price = e._price

    def slow_price(work, *, emit=True):
        _t.sleep(0.002)  # widen the check-then-insert window so a missing lock shows
        return real_price(work, emit=emit)

    e._price = slow_price  # type: ignore[method-assign]
    granted: list = []
    lock = threading.Lock()

    def worker():
        try:
            r = e.reserve(StepInput(tokens=100_000, model="m"))  # $0.10 each
        except ReservationRefused:
            return
        with lock:
            granted.append(r)

    threads = [threading.Thread(target=worker) for _ in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(granted) == 10
    for r in granted:
        e.commit(r, StepInput(tokens=100_000, model="m"))
    assert e.spend_usd == pytest.approx(1.0)


# --- I-03/I-05 safe defaults ----------------------------------------------

def test_empty_steps_do_not_drain_pressure_by_default():
    e, _ = eng()
    e.step(StepInput(tokens=50_000))
    before = e.pressure
    for _ in range(100):
        e.step(StepInput())
    assert e.pressure == before


def test_unpriced_model_charged_at_highest_price_by_default():
    e, sink = eng(model_costs={"cheap": 0.5, "frontier": 15.0}, budget_usd=20.0,
                  token_coefficient=0.0)
    e.step(StepInput(tokens=1_000_000, model="made-up-model"))
    assert e.spend_usd == pytest.approx(15.0)
    e.step(StepInput(tokens=1_000_000))  # no model at all
    assert e.spend_usd == pytest.approx(30.0)
    assert e.lifecycle is Lifecycle.LOCKED
    assert len(sink.by_kind("engine.unpriced_model")) == 2


def test_v1_profile_restores_1x_semantics():
    cfg = PressureConfig.v1(model_costs={"m": 1.0})
    assert cfg.empty_step_dissipation is True
    assert cfg.unpriced_model_usd_per_million == 0.0


# --- I-08/I-09/I-10 consent 2.0 ------------------------------------------

def test_default_algorithm_is_inferred_from_an_asymmetric_key():
    priv, pub = generate_ed25519_keypair()
    iss = ConsentIssuer(signing_key=priv, audience="proxy")
    assert iss.algorithm == "EdDSA"
    tok = iss.issue("alice", ["llm"], execution_id="e1").token
    v = ConsentVerifier(verification_key=pub, audience="proxy")
    assert v.algorithm == "EdDSA"
    assert v.verify(tok, execution_id="e1").subject == "alice"
    with pytest.raises(InvalidToken):
        v.verify(tok, execution_id="e2")


def test_a_public_key_cannot_mint_tokens():
    _, pub = generate_ed25519_keypair()
    with pytest.raises(ValueError, match="public key"):
        ConsentIssuer(signing_key=pub, audience="proxy")


def test_shared_secret_needs_explicit_hs256():
    with pytest.raises(ValueError, match="HS256"):
        ConsentIssuer(signing_key=generate_hs256_secret(), audience="a")


def test_audience_is_required():
    priv, pub = generate_ed25519_keypair()
    with pytest.raises(ValueError, match="audience"):
        ConsentIssuer(signing_key=priv)
    with pytest.raises(ValueError, match="audience"):
        ConsentVerifier(verification_key=pub)


def test_token_without_aud_is_refused_by_2x_verifier():
    key = generate_hs256_secret()
    tok = ConsentIssuer.v1(signing_key=key).issue("a", ["x"], execution_id="e").token
    with pytest.raises(InvalidToken):
        ConsentVerifier(verification_key=key, algorithm="HS256", audience="svc").verify(
            tok, execution_id="e")


def test_unbound_token_refused_for_an_execution_by_default():
    priv, pub = generate_ed25519_keypair()
    tok = ConsentIssuer(signing_key=priv, audience="p").issue("a", ["x"]).token
    with pytest.raises(InvalidToken, match="not bound"):
        ConsentVerifier(verification_key=pub, audience="p").verify(tok, execution_id="e1")


def test_algorithm_confusion_public_key_as_hmac_secret_refused():
    # Classic attack: sign HS256 with the verifier's *public* key as the secret.
    import time

    import jwt
    _, pub = generate_ed25519_keypair()
    v = ConsentVerifier(verification_key=pub, audience="p")
    now = int(time.time())
    try:
        forged = jwt.encode({"iss": "iaiso", "sub": "m", "iat": now, "exp": now + 60,
                             "jti": "x", "aud": "p", "scopes": ["*"]},
                            pub, algorithm="HS256")
    except jwt.InvalidKeyError:
        return  # PyJWT itself refuses a PEM as an HMAC key: attack impossible
    with pytest.raises(InvalidToken):
        v.verify(forged)


# --- I-24 a release discards agent state ---------------------------------

class Chatty:
    built = 0

    def __init__(self):
        Chatty.built += 1
        self.memory: list[str] = []

    def run(self, task: str) -> dict:
        self.memory.append(task)
        return {"output": "ok", "usage": {"total_tokens": 1}}


def test_release_rebuilds_the_agent_from_the_factory():
    Chatty.built = 0
    sink = MemorySink()
    w = PressureWrapper(None, agent_factory=Chatty, audit_sink=sink,
                        config=PressureConfig(tool_coefficient=0.6,
                                              post_release_lock=False))
    first = w._agent
    w.run("remember the secret plan")
    assert first.memory == ["remember the secret plan"]
    assert w.record_tool_call(count=2) is StepOutcome.RELEASED
    assert w._agent is None  # nothing references the old agent
    w.run("what was the plan?")
    assert w._agent is not first
    assert w._agent.memory == ["what was the plan?"]
    assert Chatty.built == 2 and w.agent_generation == 2
    kinds = [e.kind for e in sink.events]
    assert "wrapper.agent_discarded" in kinds and "wrapper.agent_rebuilt" in kinds


def test_reset_rebuilds_too():
    w = PressureWrapper(None, agent_factory=Chatty, audit_sink=MemorySink())
    w.run("a")
    w.reset()
    w.run("b")
    assert w._agent.memory == ["b"]


def test_without_factory_state_kept_is_audited():
    sink = MemorySink()
    w = PressureWrapper(Chatty(), audit_sink=sink,
                        config=PressureConfig(tool_coefficient=0.6, post_release_lock=False))
    w.run("x")
    w.record_tool_call(count=2)
    assert sink.by_kind("wrapper.agent_state_kept")
    assert w._agent.memory == ["x"]


def test_needs_agent_or_factory():
    with pytest.raises(TypeError):
        PressureWrapper(None)
