"""`python -m iaiso.proxy` — run the enforcement proxy.

Example (OpenAI, Ed25519 consent, $20 and 2M-token lifetime caps per execution):

    export OPENAI_API_KEY=sk-...            # only the proxy sees this
    export IAISO_ADMIN_TOKEN=$(python -c 'import secrets;print(secrets.token_urlsafe(32))')
    iaiso consent keygen --out consent      # consent.key stays with the issuer
    python -m iaiso.proxy --provider openai --upstream https://api.openai.com \\
        --key-env OPENAI_API_KEY --consent-key consent.pub --audience iaiso-proxy \\
        --max-total-tokens 2000000 --budget-usd 20 --model-cost gpt-4o=10 \\
        --audit-jsonl audit.jsonl

The agent then uses base_url=http://127.0.0.1:8787/v1, its consent token as
the API key, and sends `X-IAIso-Execution: <execution id>`.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from iaiso.audit import JsonlFileSink, StdoutSink
from iaiso.consent import ConsentVerifier
from iaiso.core.engine import PressureConfig
from iaiso.proxy import EnforcementProxy, ProxyConfig


def _model_cost(s: str) -> tuple[str, float]:
    name, _, price = s.partition("=")
    if not name or not price:
        raise argparse.ArgumentTypeError("use MODEL=USD_PER_MILLION")
    return name, float(price)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="iaiso-proxy", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--provider", choices=["openai", "anthropic"], required=True)
    p.add_argument("--upstream", required=True)
    p.add_argument("--key-env", required=True,
                   help="Environment variable holding the provider API key")
    p.add_argument("--consent-key", required=True,
                   help="Public PEM (EdDSA/RS256), or HMAC secret file with --consent-algorithm HS256")
    p.add_argument("--consent-algorithm", choices=["EdDSA", "RS256", "HS256"])
    p.add_argument("--consent-issuer", default="iaiso")
    p.add_argument("--audience", required=True)
    p.add_argument("--scope", default="llm", help="Scope each token must grant")
    p.add_argument("--admin-token-env", default="IAISO_ADMIN_TOKEN")
    p.add_argument("--listen", default="127.0.0.1:8787")
    p.add_argument("--tls-cert")
    p.add_argument("--tls-key")
    p.add_argument("--audit-jsonl", help="Audit log path (default: stdout)")
    p.add_argument("--strict", action="store_true", help="enforcement_mode=strict")
    p.add_argument("--calibration-artifact")
    p.add_argument("--max-total-tokens", type=int, default=0)
    p.add_argument("--max-total-tool-calls", type=int, default=0)
    p.add_argument("--max-total-steps", type=int, default=0)
    p.add_argument("--budget-usd", type=float, default=0.0)
    p.add_argument("--model-cost", type=_model_cost, action="append", default=[])
    p.add_argument("--token-coefficient", type=float, default=0.015)
    p.add_argument("--tool-coefficient", type=float, default=0.08)
    p.add_argument("--escalation-threshold", type=float, default=0.85)
    p.add_argument("--release-threshold", type=float, default=0.95)
    return p


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    api_key = os.environ.get(a.key_env, "")
    if not api_key:
        print(f"error: ${a.key_env} is empty", file=sys.stderr)
        return 2
    admin = os.environ.get(a.admin_token_env) or None
    key = Path(a.consent_key).read_bytes()
    verifier = ConsentVerifier(verification_key=key, algorithm=a.consent_algorithm,
                               issuer=a.consent_issuer, audience=a.audience)
    pressure = PressureConfig(
        token_coefficient=a.token_coefficient, tool_coefficient=a.tool_coefficient,
        escalation_threshold=a.escalation_threshold, release_threshold=a.release_threshold,
        max_total_tokens=a.max_total_tokens, max_total_tool_calls=a.max_total_tool_calls,
        max_total_steps=a.max_total_steps, budget_usd=a.budget_usd,
        model_costs=dict(a.model_cost) or None)
    sink = JsonlFileSink(a.audit_jsonl) if a.audit_jsonl else StdoutSink()
    proxy = EnforcementProxy(ProxyConfig(
        upstream=a.upstream, provider=a.provider, api_key=api_key, verifier=verifier,
        pressure=pressure, required_scope=a.scope, admin_token=admin, audit_sink=sink,
        enforcement_mode="strict" if a.strict else "permissive",
        calibration_artifact=a.calibration_artifact))
    host, _, port = a.listen.rpartition(":")
    srv = proxy.make_server(host or "127.0.0.1", int(port), a.tls_cert, a.tls_key)
    scheme = "https" if a.tls_cert else "http"
    print(f"iaiso-proxy listening on {scheme}://{host}:{port} -> {a.upstream} "
          f"({a.provider}); admin {'on' if admin else 'off'}", file=sys.stderr)
    try:  # nosemgrep: except-pass
        srv.serve_forever()
    except KeyboardInterrupt:  # Ctrl-C is a clean shutdown
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
