"""Tests for the Redis revocation backend.

Uses fakeredis, which implements the Redis RESP protocol in-process.
Behavior should match a real Redis 7.x server for the operations we use
(SET with EX, EXISTS, SCAN), but verification against an actual Redis
instance is required before production deployment.
"""

from __future__ import annotations

import time

import fakeredis
import pytest

from iaiso import ConsentIssuer, ConsentVerifier, RevokedToken, generate_hs256_secret
from iaiso.consent.backends import (
    FailClosedRevocationBackend,
    FailOpenRevocationBackend,
    RedisRevocationBackend,
)


@pytest.fixture
def redis_client() -> fakeredis.FakeRedis:
    return fakeredis.FakeRedis()


def test_revoke_and_check(redis_client: fakeredis.FakeRedis) -> None:
    backend = RedisRevocationBackend(redis_client)
    assert not backend.is_revoked("jti-1")
    backend.revoke("jti-1")
    assert backend.is_revoked("jti-1")


def test_ttl_expires_revocation(redis_client: fakeredis.FakeRedis) -> None:
    backend = RedisRevocationBackend(redis_client, default_ttl_seconds=1)
    backend.revoke("jti-short")
    assert backend.is_revoked("jti-short")
    # Advance fakeredis's clock
    redis_client.time = lambda: (int(time.time()) + 2, 0)
    # fakeredis respects real-time TTLs; sleep for test
    time.sleep(1.1)
    assert not backend.is_revoked("jti-short")


def test_key_prefix_isolation(redis_client: fakeredis.FakeRedis) -> None:
    backend_a = RedisRevocationBackend(redis_client, key_prefix="tenant-a")
    backend_b = RedisRevocationBackend(redis_client, key_prefix="tenant-b")
    backend_a.revoke("shared-jti")
    assert backend_a.is_revoked("shared-jti")
    assert not backend_b.is_revoked("shared-jti")


def test_integration_with_verifier(redis_client: fakeredis.FakeRedis) -> None:
    secret = generate_hs256_secret()
    backend = RedisRevocationBackend(redis_client)
    issuer = ConsentIssuer(signing_key=secret)
    verifier = ConsentVerifier(verification_key=secret, revocation_list=backend)

    token = issuer.issue(subject="alice", scopes=["x"])
    verifier.verify(token.token)  # ok

    backend.revoke(token.jti)
    with pytest.raises(RevokedToken):
        verifier.verify(token.token)


def test_length_counts_revocations(redis_client: fakeredis.FakeRedis) -> None:
    backend = RedisRevocationBackend(redis_client, key_prefix="test")
    assert len(backend) == 0
    backend.revoke("a")
    backend.revoke("b")
    backend.revoke("c")
    assert len(backend) == 3


def test_fail_closed_wrapper() -> None:
    class BrokenBackend:
        def revoke(self, jti: str, ttl_seconds: float | None = None) -> None:
            pass

        def is_revoked(self, jti: str) -> bool:
            raise ConnectionError("simulated outage")

        def __len__(self) -> int:
            return 0

    wrapped = FailClosedRevocationBackend(BrokenBackend())
    assert wrapped.is_revoked("anything") is True


def test_fail_open_wrapper() -> None:
    class BrokenBackend:
        def revoke(self, jti: str, ttl_seconds: float | None = None) -> None:
            pass

        def is_revoked(self, jti: str) -> bool:
            raise ConnectionError("simulated outage")

        def __len__(self) -> int:
            return 0

    wrapped = FailOpenRevocationBackend(BrokenBackend())
    assert wrapped.is_revoked("anything") is False
