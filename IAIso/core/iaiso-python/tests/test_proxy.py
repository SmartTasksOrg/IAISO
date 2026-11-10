"""Enforcement proxy against a fake provider on localhost."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from iaiso import ConsentIssuer, ConsentVerifier, PressureConfig, generate_ed25519_keypair
from iaiso.audit import MemorySink
from iaiso.proxy import EnforcementProxy, ProxyConfig

REAL_KEY = "sk-real-provider-key-never-leaves-the-proxy"
ADMIN = "a" * 40
PRIV, PUB = generate_ed25519_keypair()
ISSUER = ConsentIssuer(signing_key=PRIV, audience="iaiso-proxy")


class Upstream:
    """Fake OpenAI/Anthropic: records what it received, returns scripted JSON."""

    def __init__(self) -> None:
        self.seen: list[dict] = []
        self.reply: dict | None = None
        self.status = 200
        up = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                up.seen.append({"path": self.path, "body": body,
                                "headers": {k.lower(): v for k, v in self.headers.items()}})
                reply = up.reply if up.reply is not None else {
                    "id": "x", "choices": [{"message": {"content": "hi"}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 20}}
                raw = json.dumps(reply).encode()
                self.send_response(up.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.srv.server_port}"


@pytest.fixture
def stack():
    up = Upstream()
    sink = MemorySink()
    made = {}

    def build(provider="openai", **pressure):
        base = {"max_total_tokens": 100_000, "token_coefficient": 0.001}
        base.update(pressure)
        proxy = EnforcementProxy(ProxyConfig(
            upstream=up.url, provider=provider, api_key=REAL_KEY,
            verifier=ConsentVerifier(verification_key=PUB, audience="iaiso-proxy"),
            pressure=PressureConfig(**base), admin_token=ADMIN, audit_sink=sink))
        srv = proxy.make_server("127.0.0.1", 0)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        made["srv"] = srv
        return proxy, f"http://127.0.0.1:{srv.server_port}"

    yield up, sink, build
    up.srv.shutdown()
    if "srv" in made:
        made["srv"].shutdown()


def call(base, path="/v1/chat/completions", body=None, token=None, execution="e1",
         headers=None):
    body = body if body is not None else {"model": "gpt-4o", "max_tokens": 50,
                                          "messages": [{"role": "user", "content": "hi"}]}
    h = {"Content-Type": "application/json"}
    if execution:
        h["X-IAIso-Execution"] = execution
    if token is None:
        token = ISSUER.issue("agent-1", ["llm"], execution_id=execution or "e1").token
    if token:
        h["Authorization"] = f"Bearer {token}"
    h.update(headers or {})
    req = urllib.request.Request(base + path, data=json.dumps(body).encode(), headers=h,
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, dict(r.headers), json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), json.loads(e.read())


def admin(base, ex, action, token=ADMIN):
    req = urllib.request.Request(f"{base}/iaiso/admin/{ex}/{action}", data=b"{}",
                                 headers={"Authorization": f"Bearer {token}",
                                          "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_forwards_with_the_real_key_and_accounts_provider_usage(stack):
    up, _sink, build = stack
    proxy, base = build()
    status, headers, body = call(base)
    assert status == 200 and body["choices"][0]["message"]["content"] == "hi"
    sent = up.seen[0]["headers"]
    assert sent["authorization"] == f"Bearer {REAL_KEY}"
    assert REAL_KEY not in json.dumps(headers) + json.dumps(body)
    assert proxy.engine("e1").totals == {"tokens": 30, "tool_calls": 0, "steps": 1}
    assert headers["X-IAIso-Lifecycle"] == "running"
    assert headers["X-Content-Type-Options"] == "nosniff"  # ZAP 10021
    assert headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("token,code", [("", 401), ("garbage", 401)])
def test_bad_consent_refused(stack, token, code):
    up, _, build = stack
    _, base = build()
    assert call(base, token=token)[0] == code
    assert up.seen == []


def test_token_for_another_execution_refused(stack):
    up, _, build = stack
    _, base = build()
    tok = ISSUER.issue("agent-1", ["llm"], execution_id="other").token
    assert call(base, token=tok, execution="e1")[0] == 401
    assert up.seen == []


def test_unbound_token_refused(stack):
    _, _, build = stack
    _, base = build()
    assert call(base, token=ISSUER.issue("a", ["llm"]).token)[0] == 401


def test_wrong_scope_refused(stack):
    _, _, build = stack
    _, base = build()
    tok = ISSUER.issue("a", ["tools"], execution_id="e1").token
    assert call(base, token=tok)[0] == 403


def test_streaming_and_missing_limits_refused(stack):
    up, _, build = stack
    _, base = build()
    assert call(base, body={"model": "m", "max_tokens": 5, "stream": True})[0] == 400
    assert call(base, body={"model": "m", "messages": []})[0] == 400
    assert call(base, body={"model": "m", "max_tokens": -5})[0] == 400
    assert call(base, body={"model": "m", "max_tokens": 5, "n": 0})[0] == 400
    assert up.seen == []


def test_path_not_proxied(stack):
    _, _, build = stack
    _, base = build()
    assert call(base, path="/v1/files")[0] == 404


def test_reservation_refuses_requests_that_cannot_fit_the_cap(stack):
    up, _sink, build = stack
    _, base = build(max_total_tokens=1_000)
    status, _, body = call(base, body={"model": "m", "max_tokens": 5_000, "messages": []})
    assert status == 429 and body["error"]["type"] == "refused_tokens"
    assert up.seen == []


def test_budget_reservation(stack):
    up, _, build = stack
    _, base = build(model_costs={"gpt-4o": 10.0}, budget_usd=0.001)
    # 1000 output tokens at $10/M = $0.01 > $0.001
    status, _, body = call(base, body={"model": "gpt-4o", "max_tokens": 1000, "messages": []})
    assert status == 429 and body["error"]["type"] == "refused_budget"
    assert up.seen == []


def test_unpriced_model_is_charged_not_free(stack):
    _, _, build = stack
    _, base = build(model_costs={"gpt-4o": 10.0}, budget_usd=0.001)
    status, _, _ = call(base, body={"model": "brand-new-model", "max_tokens": 1000,
                                    "messages": []})
    assert status == 429


def test_cap_exhaustion_locks_then_admin_reset(stack):
    up, _, build = stack
    up.reply = {"usage": {"prompt_tokens": 600, "completion_tokens": 400}}
    _proxy, base = build(max_total_tokens=1_500)
    assert call(base, body={"model": "m", "max_tokens": 100, "messages": []})[0] == 200
    # 1000 used; reservation (~40 + 100) fits; usage reports 1000 more -> cap -> locked
    assert call(base, body={"model": "m", "max_tokens": 100, "messages": []})[0] == 200
    status, _, body = call(base, body={"model": "m", "max_tokens": 100, "messages": []})
    assert status == 423 and body["error"]["lifecycle"] == "locked"
    assert admin(base, "e1", "reset", token="x" * 40)[0] == 403
    assert admin(base, "e1", "reset")[0] == 200
    up.reply = None
    assert call(base)[0] == 200


def test_escalation_needs_operator_approval_per_request(stack):
    up, _, build = stack
    up.reply = {"usage": {"prompt_tokens": 0, "completion_tokens": 900}}
    proxy, base = build(token_coefficient=1.0, dissipation_per_step=0.0)  # 900 tok -> 0.9
    assert call(base)[0] == 200
    assert proxy.engine("e1").lifecycle.value == "escalated"
    up.reply = {"usage": {"prompt_tokens": 0, "completion_tokens": 0}}
    assert call(base)[0] == 409
    assert admin(base, "e1", "approve")[0] == 200
    assert call(base)[0] == 200
    assert call(base)[0] == 409  # approval was one-shot


def test_usage_missing_charges_the_full_reservation(stack):
    up, sink, build = stack
    up.reply = {"choices": [{"message": {"content": "no usage here"}}]}
    proxy, base = build()
    assert call(base)[0] == 200
    assert proxy.engine("e1").totals["tokens"] >= 50  # at least max_tokens
    assert sink.by_kind("proxy.usage_missing")


def test_provider_error_cancels_the_reservation(stack):
    up, _sink, build = stack
    up.status, up.reply = 400, {"error": {"message": "bad request"}}
    proxy, base = build()
    assert call(base)[0] == 400
    e = proxy.engine("e1")
    assert e.totals["tokens"] == 0 and e.outstanding_reservations == 0


def test_tool_calls_from_the_response_are_counted(stack):
    up, _, build = stack
    up.reply = {"choices": [{"message": {"tool_calls": [{"id": "1"}, {"id": "2"}]}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1}}
    proxy, base = build()
    call(base)
    assert proxy.engine("e1").totals["tool_calls"] == 2


def test_anthropic_consent_via_x_api_key(stack):
    up, _, build = stack
    up.reply = {"content": [{"type": "text", "text": "hi"}, {"type": "tool_use"}],
                "usage": {"input_tokens": 5, "output_tokens": 7}}
    proxy, base = build(provider="anthropic")
    tok = ISSUER.issue("a", ["llm"], execution_id="e1").token
    status, _, _ = call(base, path="/v1/messages", token="",
                        headers={"x-api-key": tok, "anthropic-version": "2023-06-01"})
    assert status == 200
    assert up.seen[0]["headers"]["x-api-key"] == REAL_KEY
    assert proxy.engine("e1").totals == {"tokens": 12, "tool_calls": 1, "steps": 1}


def test_execution_header_required_and_validated(stack):
    _, _, build = stack
    _, base = build()
    assert call(base, execution="")[0] == 400
    assert call(base, execution="../../etc", token="x")[0] == 400


def test_config_refuses_plain_http_upstream_and_short_admin_token():
    v = ConsentVerifier(verification_key=PUB, audience="p")
    with pytest.raises(ValueError, match="https"):
        ProxyConfig(upstream="http://api.openai.com", provider="openai", api_key="k",
                    verifier=v, pressure=PressureConfig())
    with pytest.raises(ValueError, match="admin_token"):
        ProxyConfig(upstream="https://api.openai.com", provider="openai", api_key="k",
                    verifier=v, pressure=PressureConfig(), admin_token="short")


def test_strict_proxy_refuses_uncapped_config_at_startup():
    from iaiso.core.engine import StrictModeError
    with pytest.raises(StrictModeError):
        EnforcementProxy(ProxyConfig(
            upstream="https://api.openai.com", provider="openai", api_key="k",
            verifier=ConsentVerifier(verification_key=PUB, audience="p"),
            pressure=PressureConfig(token_coefficient=0.011), audit_sink=MemorySink(),
            enforcement_mode="strict"))


def test_concurrent_requests_cannot_overspend(stack):
    up, _, build = stack
    up.reply = {"usage": {"prompt_tokens": 0, "completion_tokens": 100}}
    proxy, base = build(max_total_tokens=1_200, token_coefficient=0.0)
    codes: list[int] = []
    lk = threading.Lock()

    def go():
        c = call(base, body={"model": "m", "max_tokens": 100, "messages": []})[0]
        with lk:
            codes.append(c)

    ts = [threading.Thread(target=go) for _ in range(30)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert proxy.engine("e1").totals["tokens"] <= 1_200
    assert codes.count(200) == len(up.seen)
    assert set(codes) <= {200, 429, 423}
