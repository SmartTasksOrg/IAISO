"""Persistent backends for the consent revocation list.

The in-memory `RevocationList` in `iaiso.consent` is fine for tests and
single-process deployments where rebuild-on-startup is acceptable. Multi-
process deployments, or deployments where revocations must survive a restart,
need a persistent backend.

This module defines `RevocationBackend`, a minimal protocol, and ships a
Redis reference implementation. Implement the protocol against any store
(PostgreSQL, DynamoDB, etcd, a custom service) — the rest of IAIso is
agnostic.

Install:  pip install iaiso[redis]
"""

from __future__ import annotations

import time
from typing import Protocol

try:
    import redis
    _REDIS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _REDIS_AVAILABLE = False


class RevocationBackend(Protocol):
    """Protocol for a persistent revocation store.

    Implementations must be safe for concurrent access from multiple
    processes. `is_revoked()` is on the hot path of every token check; it
    must be fast (< 5 ms typical) and tolerate transient backend outages
    gracefully (see `FailClosedPolicy` / `FailOpenPolicy` in consumers).
    """

    def revoke(self, jti: str, ttl_seconds: float | None = None) -> None:
        """Mark `jti` as revoked. If `ttl_seconds` is set, the entry is
        automatically removed after that duration (useful to avoid
        unbounded growth: a token that has expired on its own does not
        need to remain on the revocation list)."""
        ...

    def is_revoked(self, jti: str) -> bool:
        """Return True if `jti` has been revoked and not yet expired."""
        ...

    def __len__(self) -> int:
        """Current size of the revocation list. May be approximate."""
        ...


class RedisRevocationBackend:
    """Redis-backed revocation list.

    Layout: keys are `{key_prefix}:{jti}` with a boolean-ish value and an
    optional TTL. Presence of the key == revoked.

    Example:
        import redis
        from iaiso.consent.backends import RedisRevocationBackend
        from iaiso.consent import ConsentVerifier

        client = redis.Redis.from_url("redis://localhost:6379/0")
        backend = RedisRevocationBackend(client)
        verifier = ConsentVerifier(
            verification_key=secret,
            revocation_list=backend,   # satisfies the list protocol
        )

    Note on the protocol: `ConsentVerifier` expects something with an
    `is_revoked(jti) -> bool` method. This class satisfies that interface.

    Verification Required Before Production:
        This backend has been tested against `fakeredis` (which implements
        the Redis RESP protocol in-process). Behavior should match a real
        Redis server, but end-to-end testing against your actual Redis
        deployment is required before production use. In particular:

        - Network partition behavior: decide whether IAIso should fail-open
          (allow tokens if Redis is unreachable) or fail-closed (deny all
          tokens if Redis is unreachable). Default here is fail-closed via
          the exception raised by redis-py; wrap this backend to change
          that policy.
        - TTL semantics: Redis TTL is per-key, honored by `EXPIRE`. Verify
          your Redis version supports this (all versions >= 2.6 do, but
          some hosted Redis services disable `EXPIRE` on certain plans).
        - Key prefix collisions: set `key_prefix` to a unique value for
          your IAIso deployment.
    """

    def __init__(
        self,
        client: "redis.Redis",
        *,
        key_prefix: str = "iaiso:revoked",
        default_ttl_seconds: float | None = 86_400.0,
    ) -> None:
        if not _REDIS_AVAILABLE:  # pragma: no cover
            raise ImportError(
                "redis is required for RedisRevocationBackend. "
                "Install with `pip install iaiso[redis]` or `pip install redis`."
            )
        self._client = client
        self._prefix = key_prefix
        self._default_ttl = default_ttl_seconds

    def _key(self, jti: str) -> str:
        return f"{self._prefix}:{jti}"

    def revoke(self, jti: str, ttl_seconds: float | None = None) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        key = self._key(jti)
        # Use SET with EX for atomicity — SET key val + EXPIRE key ttl has
        # a race where the key exists briefly without TTL.
        if ttl is not None and ttl > 0:
            self._client.set(key, "1", ex=int(ttl))
        else:
            self._client.set(key, "1")

    def is_revoked(self, jti: str) -> bool:
        return bool(self._client.exists(self._key(jti)))

    def __len__(self) -> int:
        """Approximate count. Uses SCAN to avoid blocking on large lists.

        This is O(N) over the revocation list and should not be called
        frequently. For production metrics, use `DBSIZE` on a dedicated
        Redis database or track count externally.
        """
        count = 0
        for _ in self._client.scan_iter(match=f"{self._prefix}:*", count=1000):
            count += 1
        return count


class FailClosedRevocationBackend:
    """Wraps a `RevocationBackend` so that backend exceptions cause tokens
    to be treated as revoked (fail-closed). Use this when token replay is a
    higher risk than occasional legitimate denials during Redis outages.
    """

    def __init__(self, inner: RevocationBackend) -> None:
        self._inner = inner

    def revoke(self, jti: str, ttl_seconds: float | None = None) -> None:
        self._inner.revoke(jti, ttl_seconds)

    def is_revoked(self, jti: str) -> bool:
        try:
            return self._inner.is_revoked(jti)
        except Exception:  # noqa: BLE001
            return True  # fail-closed: treat as revoked on error

    def __len__(self) -> int:
        try:
            return len(self._inner)  # type: ignore[arg-type]
        except Exception:  # noqa: BLE001
            return 0


class FailOpenRevocationBackend:
    """Wraps a `RevocationBackend` so that backend exceptions cause tokens
    to be treated as NOT revoked (fail-open). Use this when service
    availability matters more than tight revocation, and rely on short
    token TTLs to bound the window of a replayed token.
    """

    def __init__(self, inner: RevocationBackend) -> None:
        self._inner = inner

    def revoke(self, jti: str, ttl_seconds: float | None = None) -> None:
        self._inner.revoke(jti, ttl_seconds)

    def is_revoked(self, jti: str) -> bool:
        try:
            return self._inner.is_revoked(jti)
        except Exception:  # noqa: BLE001
            return False  # fail-open: treat as valid on error

    def __len__(self) -> int:
        try:
            return len(self._inner)  # type: ignore[arg-type]
        except Exception:  # noqa: BLE001
            return 0
