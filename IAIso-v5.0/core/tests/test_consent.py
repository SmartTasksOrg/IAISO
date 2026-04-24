"""Tests for ConsentScope issuance and verification."""

from __future__ import annotations

import time

import pytest

from iaiso import (
    ConsentIssuer,
    ConsentVerifier,
    ExpiredToken,
    InsufficientScope,
    InvalidToken,
    RevocationList,
    RevokedToken,
    generate_hs256_secret,
)


@pytest.fixture
def secret() -> str:
    return generate_hs256_secret()


def test_issue_and_verify_roundtrip(secret: str) -> None:
    issuer = ConsentIssuer(signing_key=secret)
    verifier = ConsentVerifier(verification_key=secret)

    issued = issuer.issue(subject="alice", scopes=["tools.search", "tools.fetch"])
    verified = verifier.verify(issued.token)

    assert verified.subject == "alice"
    assert "tools.search" in verified.scopes
    assert verified.jti == issued.jti


def test_scope_prefix_match(secret: str) -> None:
    issuer = ConsentIssuer(signing_key=secret)
    verifier = ConsentVerifier(verification_key=secret)

    issued = issuer.issue(subject="alice", scopes=["tools"])
    verified = verifier.verify(issued.token)

    assert verified.grants("tools.search")
    assert verified.grants("tools.fetch.bulk")
    assert not verified.grants("admin")
    assert not verified.grants("tool")  # not a prefix at segment boundary


def test_scope_exact_match(secret: str) -> None:
    issuer = ConsentIssuer(signing_key=secret)
    verifier = ConsentVerifier(verification_key=secret)

    issued = issuer.issue(subject="alice", scopes=["tools.search"])
    verified = verifier.verify(issued.token)

    assert verified.grants("tools.search")
    assert not verified.grants("tools.fetch")


def test_require_raises_on_insufficient(secret: str) -> None:
    issuer = ConsentIssuer(signing_key=secret)
    verifier = ConsentVerifier(verification_key=secret)
    issued = issuer.issue(subject="alice", scopes=["tools.search"])
    verified = verifier.verify(issued.token)

    with pytest.raises(InsufficientScope) as exc_info:
        verified.require("admin.delete")
    assert exc_info.value.requested == "admin.delete"


def test_expired_token_rejected(secret: str) -> None:
    issuer = ConsentIssuer(signing_key=secret, default_ttl_seconds=1)
    verifier = ConsentVerifier(verification_key=secret, leeway_seconds=0)

    issued = issuer.issue(subject="alice", scopes=["x"])
    time.sleep(1.1)
    with pytest.raises(ExpiredToken):
        verifier.verify(issued.token)


def test_wrong_key_fails(secret: str) -> None:
    issuer = ConsentIssuer(signing_key=secret)
    verifier = ConsentVerifier(verification_key=generate_hs256_secret())
    issued = issuer.issue(subject="alice", scopes=["x"])
    with pytest.raises(InvalidToken):
        verifier.verify(issued.token)


def test_tampered_token_fails(secret: str) -> None:
    issuer = ConsentIssuer(signing_key=secret)
    verifier = ConsentVerifier(verification_key=secret)
    issued = issuer.issue(subject="alice", scopes=["x"])

    # Flip a character in the payload segment
    parts = issued.token.split(".")
    parts[1] = parts[1][:-2] + ("AA" if parts[1][-2:] != "AA" else "BB")
    tampered = ".".join(parts)

    with pytest.raises(InvalidToken):
        verifier.verify(tampered)


def test_revocation_list(secret: str) -> None:
    issuer = ConsentIssuer(signing_key=secret)
    revocations = RevocationList()
    verifier = ConsentVerifier(
        verification_key=secret, revocation_list=revocations
    )

    issued = issuer.issue(subject="alice", scopes=["x"])
    verifier.verify(issued.token)  # ok

    revocations.revoke(issued.jti)
    with pytest.raises(RevokedToken):
        verifier.verify(issued.token)


def test_execution_binding(secret: str) -> None:
    issuer = ConsentIssuer(signing_key=secret)
    verifier = ConsentVerifier(verification_key=secret)

    bound = issuer.issue(subject="alice", scopes=["x"], execution_id="exec-A")

    # Matching execution: ok
    verifier.verify(bound.token, execution_id="exec-A")

    # Wrong execution: rejected
    with pytest.raises(InvalidToken):
        verifier.verify(bound.token, execution_id="exec-B")

    # No execution requested: ok even if token is bound
    verifier.verify(bound.token)


def test_unbound_token_works_for_any_execution(secret: str) -> None:
    issuer = ConsentIssuer(signing_key=secret)
    verifier = ConsentVerifier(verification_key=secret)

    unbound = issuer.issue(subject="alice", scopes=["x"])
    verifier.verify(unbound.token, execution_id="any-exec")
