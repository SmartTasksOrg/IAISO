"""ConsentScope — signed, time-bounded, scope-limited authorization tokens.

A ConsentScope is a JWT that authorizes a specific execution to perform a
specific set of actions within a specific time window. The engine (or middleware
built on it) should require a valid, unexpired token matching the requested
scope before allowing a tool call or external effect.

Scope grammar:
    scope ::= domain ("." domain)*
    domain ::= [a-z0-9_-]+

A request for scope `a.b.c` is satisfied by a token granting any prefix:
`a`, `a.b`, or `a.b.c`. A token granting `a.b` does NOT satisfy a request
for `a.c` or `a.b.c.d` — prefix matching is one-directional.

Supported algorithms: HS256 (symmetric, default) and RS256 (asymmetric).
For production, prefer RS256 with keys rotated via your existing key
management infrastructure.
"""

from __future__ import annotations

import secrets
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

import jwt

Algorithm = Literal["HS256", "RS256"]


class ConsentError(Exception):
    """Base class for consent-related errors."""


class InvalidToken(ConsentError):
    """The token is malformed, has a bad signature, or is otherwise unverifiable."""


class ExpiredToken(ConsentError):
    """The token's expiry (exp claim) has passed."""


class RevokedToken(ConsentError):
    """The token's jti is on the revocation list."""


class InsufficientScope(ConsentError):
    """The token is valid but does not grant the requested scope.

    Attributes:
        granted: The scopes the token actually grants.
        requested: The scope that was requested but not granted.
    """

    def __init__(self, granted: list[str], requested: str) -> None:
        super().__init__(
            f"scope '{requested}' not granted by token (granted: {granted})"
        )
        self.granted = granted
        self.requested = requested


@dataclass(frozen=True)
class ConsentScope:
    """A verified consent token ready to be attached to an execution.

    Use `ConsentIssuer.issue()` to create one and `ConsentVerifier.verify()`
    to validate an incoming token string.

    Attributes:
        token: The encoded JWT string. Pass this across process boundaries.
        subject: Identifier of the entity the token was issued to (e.g., user
            or service account).
        scopes: List of granted scope strings.
        execution_id: Optional execution binding. If set, this token is only
            valid for the named execution. Leave None for general-purpose
            tokens.
        jti: Unique token identifier, used for revocation.
        issued_at: Unix timestamp when the token was issued.
        expires_at: Unix timestamp when the token expires.
        metadata: Additional claims embedded in the token, propagated to
            audit events.
    """

    token: str
    subject: str
    scopes: list[str]
    execution_id: str | None
    jti: str
    issued_at: float
    expires_at: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def grants(self, requested: str) -> bool:
        """Check whether this token grants the requested scope."""
        return _scope_granted(self.scopes, requested)

    def require(self, requested: str) -> None:
        """Raise `InsufficientScope` if this token does not grant `requested`."""
        if not self.grants(requested):
            raise InsufficientScope(self.scopes, requested)

    def seconds_until_expiry(self, now: float | None = None) -> float:
        return self.expires_at - (now if now is not None else time.time())


def _scope_granted(granted: list[str], requested: str) -> bool:
    if not requested:
        raise ValueError("requested scope must be non-empty")
    for g in granted:
        if g == requested:
            return True
        if requested.startswith(g + "."):
            return True
    return False


@dataclass
class ConsentIssuer:
    """Signs ConsentScope tokens.

    Attributes:
        signing_key: For HS256, a symmetric secret (bytes or str). For RS256,
            a PEM-encoded private key.
        algorithm: JWT algorithm. HS256 for symmetric, RS256 for asymmetric.
        issuer: String identifying this issuer; embedded as `iss`.
        default_ttl_seconds: Default expiry window for issued tokens.
    """

    signing_key: str | bytes
    algorithm: Algorithm = "HS256"
    issuer: str = "iaiso"
    default_ttl_seconds: float = 3600.0

    def issue(
        self,
        subject: str,
        scopes: list[str],
        *,
        execution_id: str | None = None,
        ttl_seconds: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ConsentScope:
        now = time.time()
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds
        exp = now + ttl
        jti = str(uuid.uuid4())

        payload: dict[str, Any] = {
            "iss": self.issuer,
            "sub": subject,
            "iat": int(now),
            "exp": int(exp),
            "jti": jti,
            "scopes": scopes,
        }
        if execution_id is not None:
            payload["execution_id"] = execution_id
        if metadata:
            payload["metadata"] = metadata

        token = jwt.encode(payload, self.signing_key, algorithm=self.algorithm)
        return ConsentScope(
            token=token,
            subject=subject,
            scopes=list(scopes),
            execution_id=execution_id,
            jti=jti,
            issued_at=now,
            expires_at=exp,
            metadata=metadata or {},
        )


class RevocationList:
    """In-memory revocation list. Replace with a persistent store for production.

    The in-memory implementation is suitable for testing and for single-process
    deployments where the revocation list is rebuilt at startup. For multi-process
    deployments, back this with Redis or a database.
    """

    def __init__(self) -> None:
        self._revoked: set[str] = set()

    def revoke(self, jti: str) -> None:
        self._revoked.add(jti)

    def is_revoked(self, jti: str) -> bool:
        return jti in self._revoked

    def __len__(self) -> int:
        return len(self._revoked)


@dataclass
class ConsentVerifier:
    """Verifies ConsentScope tokens.

    Attributes:
        verification_key: For HS256, the same secret as the issuer. For RS256,
            a PEM-encoded public key.
        algorithm: Must match the issuer's algorithm.
        issuer: Expected `iss` claim.
        revocation_list: Revocation list to consult. None disables revocation
            checks.
        leeway_seconds: Clock skew tolerance for expiry checks.
    """

    verification_key: str | bytes
    algorithm: Algorithm = "HS256"
    issuer: str = "iaiso"
    revocation_list: RevocationList | None = None
    leeway_seconds: float = 5.0

    def verify(
        self,
        token: str,
        *,
        execution_id: str | None = None,
    ) -> ConsentScope:
        """Decode and verify a token.

        Args:
            token: Encoded JWT string.
            execution_id: If provided, the token's `execution_id` claim must
                match. If the token has no `execution_id` claim, it is
                considered a general-purpose token and is accepted.

        Raises:
            InvalidToken: Signature failure, malformed token, wrong issuer,
                wrong execution binding.
            ExpiredToken: Token expired.
            RevokedToken: Token on the revocation list.
        """
        try:
            payload = jwt.decode(
                token,
                self.verification_key,
                algorithms=[self.algorithm],
                issuer=self.issuer,
                leeway=self.leeway_seconds,
                options={"require": ["exp", "iat", "jti", "sub", "iss"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise ExpiredToken(str(exc)) from exc
        except jwt.PyJWTError as exc:
            raise InvalidToken(str(exc)) from exc

        jti = payload["jti"]
        if self.revocation_list is not None and self.revocation_list.is_revoked(jti):
            raise RevokedToken(f"token {jti} has been revoked")

        token_exec = payload.get("execution_id")
        if execution_id is not None and token_exec is not None:
            if token_exec != execution_id:
                raise InvalidToken(
                    f"token bound to execution {token_exec!r}, "
                    f"requested {execution_id!r}"
                )

        return ConsentScope(
            token=token,
            subject=payload["sub"],
            scopes=list(payload.get("scopes", [])),
            execution_id=token_exec,
            jti=jti,
            issued_at=float(payload["iat"]),
            expires_at=float(payload["exp"]),
            metadata=dict(payload.get("metadata", {})),
        )


def generate_hs256_secret() -> str:
    """Generate a cryptographically strong HS256 secret. Store it in a secret manager."""
    return secrets.token_urlsafe(64)
