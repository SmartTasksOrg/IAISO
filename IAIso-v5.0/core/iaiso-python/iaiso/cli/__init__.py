"""IAIso admin CLI.

Usage:
    iaiso --help

Subcommands:
    policy validate <file>           — check a policy file for errors
    policy template <file>           — write a blank policy template
    consent issue <subject> <scope>  — issue a token (requires signing key)
    consent verify <token>           — verify a token against a key
    audit tail <jsonl-file>          — pretty-print JSONL audit events
    audit stats <jsonl-file>         — summarize events by kind
    coordinator demo                 — run a short coordinator demo

The CLI is intentionally small. It's not a replacement for a control
plane; it's what an operator uses to debug, validate configuration,
and run smoke tests.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


def cmd_policy_validate(args: argparse.Namespace) -> int:
    from iaiso.policy import PolicyError, load_policy
    try:
        policy = load_policy(args.path)
    except PolicyError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    print(f"OK: policy v{policy.version}")
    print(f"  pressure.escalation_threshold = "
          f"{policy.pressure.escalation_threshold}")
    print(f"  coordinator.aggregator        = "
          f"{policy.aggregator.name}")
    print(f"  consent.issuer                = {policy.consent.issuer}")
    return 0


def cmd_policy_template(args: argparse.Namespace) -> int:
    from iaiso.policy import dump_policy_template
    dump_policy_template(args.path)
    print(f"Wrote template to {args.path}")
    return 0


def cmd_consent_issue(args: argparse.Namespace) -> int:
    from iaiso import ConsentIssuer, generate_hs256_secret

    if args.key:
        secret = Path(args.key).read_bytes()
    else:
        secret = generate_hs256_secret()
        print("WARNING: no --key provided; generated ephemeral secret.",
              file=sys.stderr)
        print(f"  Secret (base64): {secret.hex()}", file=sys.stderr)

    issuer = ConsentIssuer(
        signing_key=secret,
        issuer=args.issuer or "iaiso-cli",
    )
    token = issuer.issue(
        subject=args.subject,
        scopes=args.scope,
        ttl_seconds=args.ttl,
    )
    print(token.token)
    return 0


def cmd_consent_verify(args: argparse.Namespace) -> int:
    from iaiso import ConsentError, ConsentVerifier

    secret = Path(args.key).read_bytes()
    verifier = ConsentVerifier(
        verification_key=secret,
        issuer=args.issuer or "iaiso",
    )
    try:
        scope = verifier.verify(args.token)
    except ConsentError as exc:
        print(f"INVALID: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(f"OK: subject={scope.subject} scopes={scope.scopes} "
          f"expires_at={scope.expires_at}")
    return 0


def cmd_audit_tail(args: argparse.Namespace) -> int:
    from iaiso.audit import AuditEvent  # noqa: F401
    path = Path(args.path)
    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        return 1
    count = 0
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                print(f"[skipped non-JSON line: {line[:60]}]", file=sys.stderr)
                continue
            ts = obj.get("timestamp", 0)
            kind = obj.get("kind", "?")
            eid = obj.get("execution_id", "?")
            data = obj.get("data", {})
            summary = ", ".join(f"{k}={v}" for k, v in data.items()
                                if not isinstance(v, (dict, list)))[:120]
            print(f"{ts:.3f}  {kind:32s}  exec={eid[:24]}  {summary}")
            count += 1
            if args.limit and count >= args.limit:
                break
    return 0


def cmd_audit_stats(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        return 1
    counts: Counter[str] = Counter()
    executions: set[str] = set()
    total = 0
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            counts[obj.get("kind", "?")] += 1
            executions.add(obj.get("execution_id", "?"))
            total += 1
    print(f"Total events:        {total}")
    print(f"Unique executions:   {len(executions)}")
    print(f"\nEvent kinds:")
    for kind, n in counts.most_common():
        print(f"  {kind:40s} {n:>8}")
    return 0


def cmd_coordinator_demo(args: argparse.Namespace) -> int:
    """Run an in-process coordinator demo to verify installation."""
    from iaiso.coordination import (
        CoordinatorConfig,
        SharedPressureCoordinator,
        SumAggregator,
    )

    def on_escalation(snap):
        print(f"  [ESCALATION] aggregate={snap.aggregate_pressure:.2f} "
              f"fleet_size={snap.active_executions}")

    coord = SharedPressureCoordinator(
        config=CoordinatorConfig(escalation_threshold=1.5,
                                 release_threshold=2.5),
        aggregator=SumAggregator(),
        on_escalation=on_escalation,
    )

    print("Registering 5 executions...")
    for i in range(5):
        coord.register(f"demo-{i}")

    print("Raising pressure on each...")
    for pressure in (0.1, 0.2, 0.3, 0.4, 0.5):
        for i in range(5):
            snap = coord.update(f"demo-{i}", pressure)
        print(f"  per-exec={pressure:.1f}  aggregate={snap.aggregate_pressure:.2f}")

    print("Done.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="iaiso",
        description="IAIso admin CLI",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # policy
    p_policy = sub.add_parser("policy", help="Policy-file tools")
    p_policy_sub = p_policy.add_subparsers(dest="policy_cmd", required=True)

    pv = p_policy_sub.add_parser("validate",
                                 help="Validate a policy file")
    pv.add_argument("path")
    pv.set_defaults(func=cmd_policy_validate)

    pt = p_policy_sub.add_parser("template",
                                 help="Write a blank policy template")
    pt.add_argument("path")
    pt.set_defaults(func=cmd_policy_template)

    # consent
    p_consent = sub.add_parser("consent", help="Consent token tools")
    p_consent_sub = p_consent.add_subparsers(dest="consent_cmd", required=True)

    ci = p_consent_sub.add_parser("issue", help="Issue a signed consent token")
    ci.add_argument("subject")
    ci.add_argument("--scope", action="append", default=[],
                    help="Scope to grant; may be given multiple times")
    ci.add_argument("--ttl", type=float, default=3600.0)
    ci.add_argument("--issuer", help="Issuer claim")
    ci.add_argument("--key", help="Path to HMAC key file; ephemeral if omitted")
    ci.set_defaults(func=cmd_consent_issue)

    cv = p_consent_sub.add_parser("verify", help="Verify a consent token")
    cv.add_argument("token")
    cv.add_argument("--key", required=True, help="Path to HMAC key file")
    cv.add_argument("--issuer", help="Expected issuer claim (default: iaiso)")
    cv.set_defaults(func=cmd_consent_verify)

    # audit
    p_audit = sub.add_parser("audit", help="Audit-log inspection")
    p_audit_sub = p_audit.add_subparsers(dest="audit_cmd", required=True)

    at = p_audit_sub.add_parser("tail", help="Pretty-print audit events")
    at.add_argument("path")
    at.add_argument("--limit", type=int, default=0,
                    help="Maximum events to print (0 = all)")
    at.set_defaults(func=cmd_audit_tail)

    astats = p_audit_sub.add_parser("stats",
                                    help="Summarize an audit log")
    astats.add_argument("path")
    astats.set_defaults(func=cmd_audit_stats)

    # coordinator
    p_coord = sub.add_parser("coordinator",
                             help="Coordinator diagnostics")
    p_coord_sub = p_coord.add_subparsers(dest="coord_cmd", required=True)

    cd = p_coord_sub.add_parser("demo",
                                help="Run a local coordinator demo")
    cd.set_defaults(func=cmd_coordinator_demo)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
