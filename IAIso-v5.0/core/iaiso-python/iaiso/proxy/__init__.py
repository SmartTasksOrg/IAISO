"""Out-of-process enforcement proxy.

In-process IAIso trusts the agent to call `engine.step()` honestly. The proxy
removes that trust: it holds the real provider API key, sits between the agent
and the LLM API, and steps the pressure engine itself from the provider's own
`usage` numbers. An agent that skips accounting simply cannot reach the model.

    agent --(consent JWT as its "API key")--> proxy --(real key)--> provider

Per request the proxy:

1. Verifies the consent token (audience, signature, expiry, revocation) and
   that it is bound to the execution named in `X-IAIso-Execution`.
2. Refuses streaming (usage would only be known after the tokens are spent)
   and requests without an output-token limit.
3. Refuses while the execution is locked (423) or escalated and not yet
   approved by an operator (409).
4. Reserves the worst case (estimated input + max output, priced) against the
   lifetime caps and budget before forwarding; refuses with 429 if it doesn't fit.
5. Forwards with the real key, reads `usage` from the response and commits it.
   A 200 without usage commits the full reservation (fail closed); a provider
   error response cancels it; a timeout or connection failure commits it.

Operators reset or approve an execution with `POST /iaiso/admin/<id>/reset`
or `/approve`, authenticated by a separate admin token.

Standard library only; run with `python -m iaiso.proxy --help`.
"""

from __future__ import annotations

import hmac
import json
import math
import re
import ssl
import threading
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from iaiso.audit import AuditEvent, AuditSink, NullSink
from iaiso.consent import ConsentError, ConsentVerifier, InsufficientScope
from iaiso.core.engine import (
    ENFORCEMENT_PERMISSIVE,
    Lifecycle,
    PressureConfig,
    PressureEngine,
    ReservationRefused,
    StepInput,
)

PROVIDER_PATHS = {
    "openai": ("/v1/chat/completions", "/v1/responses", "/v1/completions"),
    "anthropic": ("/v1/messages",),
}
_EXEC_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_FORWARD_HEADERS = ("content-type", "anthropic-version", "anthropic-beta",
                    "openai-organization", "openai-project")


@dataclass
class ProxyConfig:
    upstream: str
    """Provider base URL, e.g. https://api.openai.com. http:// only for localhost."""
    provider: str
    """"openai" or "anthropic"."""
    api_key: str = field(repr=False)
    """The real provider key. Never logged, never returned."""
    verifier: ConsentVerifier
    pressure: PressureConfig
    required_scope: str = "llm"
    admin_token: str | None = field(default=None, repr=False)
    audit_sink: AuditSink | None = None
    max_request_bytes: int = 2_000_000
    timeout_seconds: float = 120.0
    chars_per_token: float = 3.0
    """Input estimate divisor. Real tokenizers average ~4 chars/token for
    English; 3 over-reserves, which is the safe direction."""
    enforcement_mode: str = ENFORCEMENT_PERMISSIVE
    calibration_artifact: str | None = None
    max_executions: int = 10_000

    def __post_init__(self) -> None:
        if self.provider not in PROVIDER_PATHS:
            raise ValueError(f"provider must be one of {sorted(PROVIDER_PATHS)}")
        u = urllib.parse.urlsplit(self.upstream)
        local = u.hostname in ("127.0.0.1", "localhost", "::1")
        if u.scheme != "https" and not (u.scheme == "http" and local):
            raise ValueError("upstream must be https:// (http:// only for localhost)")
        if not self.api_key:
            raise ValueError("api_key is empty")
        if self.admin_token is not None and len(self.admin_token) < 32:
            raise ValueError("admin_token must be at least 32 characters")
        if not (self.chars_per_token > 0 and math.isfinite(self.chars_per_token)):
            raise ValueError("chars_per_token must be positive")
        self.upstream = self.upstream.rstrip("/")


class _Refuse(Exception):
    def __init__(self, status: int, code: str, message: str, **extra: Any) -> None:
        super().__init__(message)
        self.status, self.code, self.extra = status, code, extra


class EnforcementProxy:
    """Holds one pressure engine per execution and serves the proxy API."""

    def __init__(self, config: ProxyConfig) -> None:
        self.cfg = config
        self._audit = config.audit_sink or NullSink()
        self._engines: dict[str, PressureEngine] = {}
        self._approved: set[str] = set()
        self._lock = threading.Lock()
        # Build one engine now so a strict boot guard refuses at startup,
        # not on the first request.
        self._new_engine("__boot_check__")

    # ------------------------------------------------------------ engines

    def _new_engine(self, execution_id: str) -> PressureEngine:
        return PressureEngine(self.cfg.pressure, execution_id=execution_id,
                              audit_sink=self._audit,
                              enforcement_mode=self.cfg.enforcement_mode,
                              calibration_artifact=self.cfg.calibration_artifact)

    def engine(self, execution_id: str) -> PressureEngine:
        with self._lock:
            e = self._engines.get(execution_id)
            if e is None:
                if len(self._engines) >= self.cfg.max_executions:
                    raise _Refuse(503, "too_many_executions",
                                  "proxy is tracking the maximum number of executions")
                e = self._engines[execution_id] = self._new_engine(execution_id)
            return e

    def _emit(self, execution_id: str, kind: str, **data: Any) -> None:
        import time
        self._audit.emit(AuditEvent(execution_id=execution_id, kind=kind,
                                    timestamp=time.time(), data=data))

    # ------------------------------------------------------------- admin

    def _check_admin(self, headers: Any) -> None:
        if not self.cfg.admin_token:
            raise _Refuse(404, "admin_disabled", "admin endpoints are disabled")
        got = (headers.get("Authorization") or "").removeprefix("Bearer ").strip()
        if not hmac.compare_digest(got.encode(), self.cfg.admin_token.encode()):
            raise _Refuse(403, "forbidden", "admin token required")

    def admin(self, execution_id: str, action: str, headers: Any) -> dict[str, Any]:
        self._check_admin(headers)
        e = self.engine(execution_id)
        if action == "reset":
            e.reset(by="proxy-admin")
            self._approved.discard(execution_id)
        elif action == "approve":
            self._approved.add(execution_id)
            self._emit(execution_id, "proxy.escalation_approved")
        else:
            raise _Refuse(404, "not_found", "unknown admin action")
        return self.status(execution_id)

    def status(self, execution_id: str) -> dict[str, Any]:
        e = self.engine(execution_id)
        return {"execution_id": execution_id, "pressure": e.pressure,
                "lifecycle": e.lifecycle.value, "totals": e.totals,
                "spend_usd": e.spend_usd, "budget_remaining_usd": e.budget_remaining_usd}

    # ----------------------------------------------------------- forward

    def _consent_token(self, headers: Any) -> str:
        auth = headers.get("Authorization") or ""
        if auth.startswith("Bearer "):
            return auth[7:].strip()
        return (headers.get("x-api-key") or headers.get("X-IAIso-Consent") or "").strip()

    @staticmethod
    def _output_limit(provider: str, path: str, body: dict[str, Any]) -> int:
        keys = ("max_output_tokens",) if path == "/v1/responses" else \
            ("max_completion_tokens", "max_tokens") if provider == "openai" else ("max_tokens",)
        for k in keys:
            v = body.get(k)
            if v is not None:
                if isinstance(v, bool) or not isinstance(v, int) or v <= 0:
                    raise _Refuse(400, "bad_max_tokens", f"{k} must be a positive integer")
                n = body.get("n", 1)
                if isinstance(n, bool) or not isinstance(n, int) or n < 1:
                    raise _Refuse(400, "bad_n", "n must be a positive integer")
                return v * n
        raise _Refuse(400, "max_tokens_required",
                      f"set {' or '.join(keys)}: the proxy reserves the worst case "
                      "before forwarding")

    @staticmethod
    def usage_of(provider: str, resp: dict[str, Any]) -> tuple[int, int] | None:
        """(tokens, tool_calls) from a provider response, or None when the
        response carries no usable usage block. Never raises on odd JSON."""

        def count(v: Any) -> int:
            return v if isinstance(v, int) and not isinstance(v, bool) and v > 0 else 0

        def items(v: Any) -> list[Any]:
            return v if isinstance(v, list) else []

        u = resp.get("usage")
        if not isinstance(u, dict):
            return None
        tokens = sum(count(u.get(k)) for k in (
            "input_tokens", "output_tokens", "prompt_tokens", "completion_tokens",
            "cache_creation_input_tokens", "cache_read_input_tokens"))
        if tokens == 0:
            tokens = count(u.get("total_tokens"))
        tools = 0
        if provider == "anthropic":
            tools = sum(1 for blk in items(resp.get("content"))
                        if isinstance(blk, dict) and blk.get("type") in ("tool_use", "server_tool_use"))
        else:
            for c in items(resp.get("choices")):
                msg = c.get("message") if isinstance(c, dict) else None
                if isinstance(msg, dict):
                    tools += len(items(msg.get("tool_calls")))
            tools += sum(1 for o in items(resp.get("output"))
                         if isinstance(o, dict) and o.get("type") in ("function_call", "tool_call"))
        return tokens, tools

    def handle(self, path: str, headers: Any, raw: bytes) -> tuple[int, dict[str, str], bytes]:
        """Policy core, independent of the HTTP server (unit-testable)."""
        execution_id = (headers.get("X-IAIso-Execution") or "").strip()
        if not _EXEC_RE.match(execution_id):
            raise _Refuse(400, "execution_required",
                          "X-IAIso-Execution header (1-128 chars of [A-Za-z0-9._:-]) is required")
        if path not in PROVIDER_PATHS[self.cfg.provider]:
            raise _Refuse(404, "path_not_allowed", f"{path} is not proxied")
        try:
            scope = self.cfg.verifier.verify(self._consent_token(headers),
                                             execution_id=execution_id)
            scope.require(self.cfg.required_scope)
        except InsufficientScope as exc:
            raise _Refuse(403, "insufficient_scope", str(exc))
        except (ConsentError, ValueError) as exc:
            self._emit(execution_id, "proxy.consent_refused", error=type(exc).__name__)
            raise _Refuse(401, "consent_invalid", f"{type(exc).__name__}: {exc}")

        try:
            body = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            raise _Refuse(400, "bad_json", "request body must be JSON")
        if not isinstance(body, dict):
            raise _Refuse(400, "bad_json", "request body must be a JSON object")
        if body.get("stream"):
            raise _Refuse(400, "streaming_refused",
                          "streaming is refused: usage is only known after the tokens are spent")
        out_max = self._output_limit(self.cfg.provider, path, body)
        model = body.get("model") if isinstance(body.get("model"), str) else None

        engine = self.engine(execution_id)
        if engine.lifecycle is Lifecycle.LOCKED:
            raise _Refuse(423, "locked", "execution is locked; an operator must reset it",
                          **self.status(execution_id))
        if engine.lifecycle is Lifecycle.ESCALATED:
            with self._lock:
                approved = execution_id in self._approved
                self._approved.discard(execution_id)
            if not approved:
                raise _Refuse(409, "escalated", "execution is escalated; an operator must approve",
                              **self.status(execution_id))

        estimate = math.ceil(len(raw) / self.cfg.chars_per_token) + out_max
        try:
            res = engine.reserve(StepInput(tokens=estimate, model=model, tag="proxy.reserve"))
        except ReservationRefused as exc:
            status = 423 if exc.reason == "locked" else 429
            raise _Refuse(status, f"refused_{exc.reason}", str(exc), **self.status(execution_id))

        req = urllib.request.Request(self.cfg.upstream + path, data=raw, method="POST")
        for h in _FORWARD_HEADERS:
            if headers.get(h):
                req.add_header(h, headers.get(h))
        if self.cfg.provider == "anthropic":
            req.add_header("x-api-key", self.cfg.api_key)
            if not headers.get("anthropic-version"):
                req.add_header("anthropic-version", "2023-06-01")
        else:
            req.add_header("Authorization", f"Bearer {self.cfg.api_key}")

        try:
            # upstream scheme is validated in ProxyConfig (https, or http to localhost)
            with urllib.request.urlopen(req, timeout=self.cfg.timeout_seconds,  # nosec B310  # nosemgrep: urlopen-non-literal
                                        context=ssl.create_default_context()
                                        if self.cfg.upstream.startswith("https") else None) as r:
                status, resp_raw, ctype = r.status, r.read(), r.headers.get("content-type", "")
        except urllib.error.HTTPError as exc:
            # The provider refused; it does not bill for that.
            engine.cancel(res)
            self._emit(execution_id, "proxy.upstream_error", status=exc.code)
            return exc.code, self._meta(engine, "application/json"), exc.read()
        except Exception as exc:  # noqa: BLE001 — timeout / connection reset
            # Unknown whether the provider did the work: charge the reservation.
            engine.commit(res, StepInput(tokens=estimate, model=model, tag="proxy.unknown"))
            self._emit(execution_id, "proxy.upstream_failed", error=type(exc).__name__)
            raise _Refuse(502, "upstream_failed", f"upstream: {type(exc).__name__}")

        usage = None
        try:  # nosemgrep: except-pass
            parsed = json.loads(resp_raw)
            usage = self.usage_of(self.cfg.provider, parsed) if isinstance(parsed, dict) else None
        except ValueError:  # usage stays None: the full reservation is charged below
            pass
        if usage is None:
            self._emit(execution_id, "proxy.usage_missing", charged_tokens=estimate)
            outcome = engine.commit(res, StepInput(tokens=estimate, model=model,
                                                   tag="proxy.usage_missing"))
        else:
            outcome = engine.commit(res, StepInput(tokens=usage[0], tool_calls=usage[1],
                                                   model=model, tag="proxy.call"))
        meta = self._meta(engine, ctype or "application/json")
        meta["X-IAIso-Outcome"] = outcome.value
        return status, meta, resp_raw

    @staticmethod
    def _meta(engine: PressureEngine, ctype: str) -> dict[str, str]:
        return {"Content-Type": ctype,
                "X-IAIso-Pressure": f"{engine.pressure:.6f}",
                "X-IAIso-Lifecycle": engine.lifecycle.value}

    # ------------------------------------------------------------- server

    def make_server(self, host: str = "127.0.0.1", port: int = 8787,
                    tls_cert: str | None = None, tls_key: str | None = None
                    ) -> ThreadingHTTPServer:
        proxy = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "iaiso-proxy"
            sys_version = ""

            def log_message(self, fmt: str, *args: Any) -> None:  # no header/key leaks
                pass

            def _send(self, status: int, headers: dict[str, str], body: bytes) -> None:
                self.send_response(status)
                for k, v in headers.items():
                    self.send_header(k, v)
                # Responses are API JSON: never sniffed, framed or cached.
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _json(self, status: int, obj: dict[str, Any]) -> None:
                self._send(status, {"Content-Type": "application/json"},
                           json.dumps(obj).encode())

            def do_GET(self) -> None:
                if self.path == "/healthz":
                    return self._json(200, {"ok": True})
                m = re.match(r"^/iaiso/admin/([^/]+)$", self.path)
                try:
                    if not m:
                        raise _Refuse(404, "not_found", "not found")
                    proxy._check_admin(self.headers)
                    self._json(200, proxy.status(urllib.parse.unquote(m.group(1))))
                except _Refuse as r:
                    self._json(r.status, {"error": r.code, "message": str(r)})

            def do_POST(self) -> None:
                try:
                    length = int(self.headers.get("Content-Length") or "0")
                except ValueError:
                    length = -1
                try:
                    if length < 0 or length > proxy.cfg.max_request_bytes:
                        raise _Refuse(413, "too_large", "request body too large or unsized")
                    raw = self.rfile.read(length)
                    m = re.match(r"^/iaiso/admin/([^/]+)/(reset|approve)$", self.path)
                    if m:
                        ex = urllib.parse.unquote(m.group(1))
                        if not _EXEC_RE.match(ex):
                            raise _Refuse(400, "bad_execution", "bad execution id")
                        return self._json(200, proxy.admin(ex, m.group(2), self.headers))
                    status, headers, body = proxy.handle(self.path.split("?")[0],
                                                         self.headers, raw)
                    self._send(status, headers, body)
                except _Refuse as r:
                    self._json(r.status, {"error": {"type": r.code, "message": str(r),
                                                    **r.extra}})

        srv = ThreadingHTTPServer((host, port), Handler)
        if tls_cert:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            ctx.load_cert_chain(tls_cert, tls_key)
            srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
        return srv


__all__ = ["PROVIDER_PATHS", "EnforcementProxy", "ProxyConfig"]
