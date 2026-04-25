"""Consent vector runner. Called from iaiso.conformance.run_consent_vectors."""

from __future__ import annotations

import time
from pathlib import Path

from iaiso.conformance import VectorResult, load_vectors


def run_consent_vectors(spec_root: Path) -> list[VectorResult]:
    from iaiso.consent import (
        ConsentIssuer,
        ConsentVerifier,
        ExpiredToken,
        InvalidToken,
        RevokedToken,
        _scope_granted,
    )

    data = load_vectors(spec_root, "consent")
    shared_key = data["hs256_key_shared"]
    results: list[VectorResult] = []

    # 1. Scope match vectors
    for vec in data.get("scope_match", []):
        got = _scope_granted(vec["granted"], vec["requested"])
        if got == vec["expected"]:
            results.append(VectorResult("consent", f"scope_match/{vec['name']}", True))
        else:
            results.append(VectorResult(
                "consent", f"scope_match/{vec['name']}", False,
                message=f"expected {vec['expected']!r}, got {got!r}",
            ))

    # 2. Scope match errors
    for vec in data.get("scope_match_errors", []):
        try:
            _scope_granted(vec["granted"], vec["requested"])
            results.append(VectorResult(
                "consent", f"scope_match_error/{vec['name']}", False,
                message=f"expected error but call succeeded",
            ))
        except ValueError as exc:
            if vec["expect_error"] in str(exc):
                results.append(VectorResult("consent", f"scope_match_error/{vec['name']}", True))
            else:
                results.append(VectorResult(
                    "consent", f"scope_match_error/{vec['name']}", False,
                    message=f"got error {exc!s} but expected substring {vec['expect_error']!r}",
                ))

    # 3. Valid tokens — must verify cleanly with given key/now/execution
    for vec in data.get("valid_tokens", []):
        verifier = ConsentVerifier(
            verification_key=shared_key,
            algorithm=vec["algorithm"],
            issuer=vec["issuer"],
            leeway_seconds=0,
        )
        try:
            _with_frozen_time(vec["now"], lambda: verifier.verify(
                vec["token"], execution_id=vec.get("execution_id"),
            ))
        except Exception as exc:  # noqa: BLE001
            results.append(VectorResult(
                "consent", f"valid_token/{vec['name']}", False,
                message=f"verification failed: {type(exc).__name__}: {exc}",
            ))
            continue

        # Re-verify to check expected fields
        scope = _with_frozen_time(vec["now"], lambda: verifier.verify(
            vec["token"], execution_id=vec.get("execution_id"),
        ))
        expected = vec["expected"]
        mismatches = []
        if scope.subject != expected["sub"]:
            mismatches.append(f"subject {scope.subject!r} != {expected['sub']!r}")
        if scope.jti != expected["jti"]:
            mismatches.append(f"jti {scope.jti!r} != {expected['jti']!r}")
        if scope.scopes != expected["scopes"]:
            mismatches.append(f"scopes {scope.scopes!r} != {expected['scopes']!r}")
        if scope.execution_id != expected["execution_id"]:
            mismatches.append(f"execution_id {scope.execution_id!r} != {expected['execution_id']!r}")
        if dict(scope.metadata) != expected["metadata"]:
            mismatches.append(f"metadata {scope.metadata!r} != {expected['metadata']!r}")

        if mismatches:
            results.append(VectorResult(
                "consent", f"valid_token/{vec['name']}", False,
                message="; ".join(mismatches),
            ))
        else:
            results.append(VectorResult("consent", f"valid_token/{vec['name']}", True))

    # 4. Invalid tokens — must raise the expected error kind
    error_map = {
        "expired": ExpiredToken,
        "invalid": InvalidToken,
        "revoked": RevokedToken,
    }
    for vec in data.get("invalid_tokens", []):
        verifier = ConsentVerifier(
            verification_key=shared_key,
            algorithm=vec["algorithm"],
            issuer=vec["issuer"],
            leeway_seconds=0,
        )
        expected_cls = error_map[vec["expect_error"]]
        try:
            _with_frozen_time(vec["now"], lambda: verifier.verify(
                vec["token"], execution_id=vec.get("execution_id"),
            ))
            results.append(VectorResult(
                "consent", f"invalid_token/{vec['name']}", False,
                message=f"expected {expected_cls.__name__} but verify succeeded",
            ))
        except expected_cls:
            results.append(VectorResult("consent", f"invalid_token/{vec['name']}", True))
        except Exception as exc:  # noqa: BLE001
            results.append(VectorResult(
                "consent", f"invalid_token/{vec['name']}", False,
                message=f"expected {expected_cls.__name__} but got {type(exc).__name__}: {exc}",
            ))

    # 5. Issue-and-verify roundtrip
    for vec in data.get("issue_and_verify_roundtrip", []):
        issuer = ConsentIssuer(signing_key=shared_key, algorithm="HS256", issuer="iaiso")
        issue_args = vec["issue"]
        try:
            scope = issuer.issue(
                subject=issue_args["subject"],
                scopes=issue_args["scopes"],
                execution_id=issue_args.get("execution_id"),
                ttl_seconds=issue_args.get("ttl_seconds"),
                metadata=issue_args.get("metadata"),
            )
        except Exception as exc:  # noqa: BLE001
            results.append(VectorResult(
                "consent", f"roundtrip/{vec['name']}", False,
                message=f"issue failed: {type(exc).__name__}: {exc}",
            ))
            continue

        # Check issued fields
        exp = vec["expected_after_issue"]
        mismatches = []
        if scope.subject != exp["subject"]:
            mismatches.append(f"subject mismatch")
        if scope.scopes != exp["scopes"]:
            mismatches.append(f"scopes mismatch")
        if scope.execution_id != exp["execution_id"]:
            mismatches.append(f"execution_id mismatch")

        if mismatches:
            results.append(VectorResult(
                "consent", f"roundtrip/{vec['name']}", False,
                message="; ".join(mismatches),
            ))
            continue

        # Verify
        verifier = ConsentVerifier(
            verification_key=shared_key, algorithm="HS256", issuer="iaiso", leeway_seconds=5,
        )
        try:
            verifier.verify(
                scope.token,
                execution_id=vec.get("verify_with_execution_id"),
            )
            results.append(VectorResult("consent", f"roundtrip/{vec['name']}", True))
        except Exception as exc:  # noqa: BLE001
            results.append(VectorResult(
                "consent", f"roundtrip/{vec['name']}", False,
                message=f"verify after issue failed: {type(exc).__name__}: {exc}",
            ))

    return results


def _with_frozen_time(frozen_now: float, fn):
    """Call `fn` with time.time() returning `frozen_now`. Restores after."""
    import iaiso.consent
    orig = iaiso.consent.time.time
    iaiso.consent.time.time = lambda: frozen_now
    try:
        # PyJWT reads time directly via datetime.now/utcnow internally — we
        # need to also patch datetime. Easier: patch PyJWT's "now".
        import jwt.api_jwt
        orig_now = None
        if hasattr(jwt.api_jwt, 'datetime'):
            import datetime as _dt
            orig_dt = jwt.api_jwt.datetime
            class _Frozen(_dt.datetime):
                @classmethod
                def now(cls, tz=None):
                    return _dt.datetime.fromtimestamp(frozen_now, tz=tz or _dt.timezone.utc)
                @classmethod
                def utcnow(cls):
                    return _dt.datetime.utcfromtimestamp(frozen_now)
            jwt.api_jwt.datetime = _Frozen
            try:
                return fn()
            finally:
                jwt.api_jwt.datetime = orig_dt
        else:
            return fn()
    finally:
        iaiso.consent.time.time = orig
