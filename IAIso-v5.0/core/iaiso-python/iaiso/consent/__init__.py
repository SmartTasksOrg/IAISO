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

Supported algorithms: EdDSA (Ed25519) and RS256 (asymmetric), and HS256
(symmetric). 2.0: there is no default algorithm. It is inferred from the key —
an Ed25519 key means EdDSA, an RSA key RS256 — and a shared secret must be
chosen explicitly with `algorithm="HS256"`. Tokens must carry an audience, and
a verifier asked about an execution refuses tokens not bound to one.
`ConsentIssuer.v1(...)` / `ConsentVerifier.v1(...)` give the 1.x behaviour.
"""

from __future__ import annotations

import secrets
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

import jwt

Algorithm = Literal["HS256", "RS256", "EdDSA"]
_ALGORITHMS = ("HS256", "RS256", "EdDSA")


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

    signing_key: Any
    algorithm: Algorithm | None = None
    """None (2.0 default): inferred from the key; a shared secret is refused
    unless HS256 is chosen explicitly."""
    issuer: str = "iaiso"
    default_ttl_seconds: float = 3600.0
    audience: str | None = None
    """Tokens carry `aud`, and only a verifier with the same audience accepts them."""
    require_audience: bool = True
    """2.0: refuse to construct an issuer without an audience."""

    def __post_init__(self) -> None:
        alg = _resolve_algorithm(self.algorithm, self.signing_key)
        self.algorithm = alg
        _check_hs256_key(alg, self.signing_key)
        if alg != "HS256":
            from cryptography.hazmat.primitives.asymmetric import ed25519, rsa
            if isinstance(_load_pem(self.signing_key), (ed25519.Ed25519PublicKey, rsa.RSAPublicKey)):
                raise ValueError("signing_key is a public key; the issuer needs the private key "
                                 "(verifiers get the public one)")
        if self.require_audience and not self.audience:
            raise ValueError("ConsentIssuer needs an audience (the service that will verify "
                             "the token); use ConsentIssuer.v1(...) for 1.x behaviour")

    @classmethod
    def v1(cls, signing_key: Any, algorithm: Algorithm = "HS256", **kw: Any) -> "ConsentIssuer":
        """1.x behaviour: HS256 by default, audience optional."""
        kw.setdefault("require_audience", False)
        return cls(signing_key=signing_key, algorithm=algorithm, **kw)

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
        if ttl <= 0:
            raise ValueError("ttl_seconds must be positive")
        if execution_id is not None:
            payload["execution_id"] = execution_id
        if metadata:
            payload["metadata"] = metadata
        if self.audience is not None:
            payload["aud"] = self.audience

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

    verification_key: Any
    algorithm: Algorithm | None = None
    issuer: str = "iaiso"
    revocation_list: RevocationList | None = None
    leeway_seconds: float = 5.0
    audience: str | None = None
    """When set, the token's `aud` must match (a token for another service is refused).
    When None, a token that carries `aud` is refused (PyJWT's behaviour)."""
    require_execution_binding: bool = True
    """2.0 default True: when `verify(..., execution_id=...)` is called, a token
    with no `execution_id` claim is refused instead of being accepted as
    general-purpose."""
    require_audience: bool = True
    """2.0: refuse to construct a verifier without an audience, and refuse
    tokens with no `aud` claim."""

    def __post_init__(self) -> None:
        alg = _resolve_algorithm(self.algorithm, self.verification_key)
        self.algorithm = alg
        _check_hs256_key(alg, self.verification_key)
        if self.require_audience and not self.audience:
            raise ValueError("ConsentVerifier needs an audience (this service's name); "
                             "use ConsentVerifier.v1(...) for 1.x behaviour")

    @classmethod
    def v1(cls, verification_key: Any, algorithm: Algorithm = "HS256",
           **kw: Any) -> "ConsentVerifier":
        """1.x behaviour: HS256 by default, audience optional, unbound tokens
        accepted for any execution."""
        kw.setdefault("require_audience", False)
        kw.setdefault("require_execution_binding", False)
        return cls(verification_key=verification_key, algorithm=algorithm, **kw)

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
                algorithms=[str(self.algorithm)],  # resolved in __post_init__
                issuer=self.issuer,
                audience=self.audience,
                leeway=self.leeway_seconds,
                options={"require": ["exp", "iat", "jti", "sub", "iss"]
                         + (["aud"] if self.require_audience else [])},
            )
        except jwt.ExpiredSignatureError as exc:
            raise ExpiredToken(str(exc)) from exc
        except jwt.PyJWTError as exc:
            raise InvalidToken(str(exc)) from exc

        jti = payload["jti"]
        if self.revocation_list is not None and self.revocation_list.is_revoked(jti):
            raise RevokedToken(f"token {jti} has been revoked")

        token_exec = payload.get("execution_id")
        if execution_id is not None and token_exec is None and self.require_execution_binding:
            raise InvalidToken(f"token is not bound to an execution; {execution_id!r} requires one")
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


MIN_HS256_KEY_BYTES = 32


def _load_pem(key: Any) -> Any:
    """Return a cryptography key object for a PEM key, else None."""
    if not isinstance(key, (str, bytes)):
        return key  # already a key object (or something PyJWT will reject)
    raw = key.encode() if isinstance(key, str) else key
    if not raw.lstrip().startswith(b"-----BEGIN"):
        return None
    from cryptography.hazmat.primitives import serialization
    try:
        return serialization.load_pem_private_key(raw, password=None)
    except (ValueError, TypeError):
        pass
    try:
        return serialization.load_pem_public_key(raw)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"unreadable PEM key: {exc}") from exc


def _resolve_algorithm(algorithm: str | None, key: Any) -> Algorithm:
    if algorithm is not None:
        known: dict[str, Algorithm] = {"HS256": "HS256", "RS256": "RS256", "EdDSA": "EdDSA"}
        if algorithm in known:
            return known[algorithm]
        raise ValueError(f"algorithm must be one of {_ALGORITHMS}, got {algorithm!r}")
    obj = _load_pem(key)
    if obj is None:
        raise ValueError("no algorithm given and the key is a shared secret; choose "
                         "algorithm='HS256' explicitly, or use an Ed25519/RSA key "
                         "(generate_ed25519_keypair())")
    from cryptography.hazmat.primitives.asymmetric import ed25519, rsa
    if isinstance(obj, (ed25519.Ed25519PrivateKey, ed25519.Ed25519PublicKey)):
        return "EdDSA"
    if isinstance(obj, (rsa.RSAPrivateKey, rsa.RSAPublicKey)):
        return "RS256"
    raise ValueError(f"unsupported key type {type(obj).__name__}; use Ed25519 or RSA")


def generate_ed25519_keypair() -> tuple[str, str]:
    """Return (private_pem, public_pem). The issuer keeps the private key; every
    verifier gets the public key, which cannot mint tokens."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519
    priv = ed25519.Ed25519PrivateKey.generate()
    return (
        priv.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                           serialization.NoEncryption()).decode(),
        priv.public_key().public_bytes(serialization.Encoding.PEM,
                                       serialization.PublicFormat.SubjectPublicKeyInfo).decode(),
    )


def _check_hs256_key(algorithm: str, key: str | bytes) -> None:
    """RFC 7518 3.2: an HS256 key must be at least 256 bits."""
    if algorithm == "HS256":
        n = len(key.encode() if isinstance(key, str) else key)
        if n < MIN_HS256_KEY_BYTES:
            raise ValueError(f"HS256 key is {n} bytes; at least {MIN_HS256_KEY_BYTES} are required "
                             "(use generate_hs256_secret())")


def generate_hs256_secret() -> str:
    """Generate a cryptographically strong HS256 secret. Store it in a secret manager."""
    return secrets.token_urlsafe(64)
