"""OIDC identity integration: enrich ConsentScope from OIDC providers.

Most organizations already run an identity provider (Okta, Auth0,
Azure AD / Microsoft Entra, Google Workspace, Keycloak, ...). Their
user and group assignments should drive what scopes an IAIso consent
token carries. This module bridges an OIDC access token or ID token
into a ConsentScope that the rest of IAIso already understands.

Two common flows:

    1. OIDC access token → ConsentScope.
       Verify the token via the provider's JWKS endpoint, then map
       OIDC claims (`scp`, `groups`, `roles`, `permissions`) into
       IAIso scope strings.

    2. OIDC ID token → ConsentScope (issued locally).
       Verify the ID token to authenticate the user, then use your
       local ConsentIssuer to mint an IAIso-specific consent token
       with scopes derived from the user's group memberships.

Provider-specific presets are provided for Okta, Auth0, and Azure AD /
Entra, but the `OIDCVerifier` works against any conforming OIDC provider
by passing `discovery_url` or `jwks_url` directly.

Install:  pip install iaiso[oidc]
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable

from iaiso import ConsentError, ConsentIssuer, ConsentScope


# -- Errors -----------------------------------------------------------------


class OIDCError(ConsentError):
    """Raised when OIDC verification or enrichment fails."""


class OIDCNetworkError(OIDCError):
    """Raised when the IdP's discovery / JWKS endpoints are unreachable."""


# -- Config -----------------------------------------------------------------


@dataclass
class OIDCProviderConfig:
    """Provider configuration.

    Pass either `discovery_url` (and we'll auto-fetch the JWKS URL from
    the well-known document) OR `jwks_url` (skip discovery).

    Attributes:
        discovery_url: `https://<issuer>/.well-known/openid-configuration`
        jwks_url: Direct JWKS endpoint; overrides discovery.
        issuer: Expected `iss` claim. If None, trust discovery's issuer.
        audience: Expected `aud` claim. If None, skip audience validation
            (not recommended in production).
        allowed_algorithms: Signing algorithms to accept. Defaults to
            RS256 + ES256 — never accept "none" or HS256 on public-key
            material from an IdP.
        jwks_cache_seconds: How long to cache the JWKS response.
            Standard JWT verifiers cache for 10 min to 1 hour.
        leeway_seconds: Clock skew tolerance on expiry/nbf checks.
    """

    discovery_url: str | None = None
    jwks_url: str | None = None
    issuer: str | None = None
    audience: str | None = None
    allowed_algorithms: tuple[str, ...] = ("RS256", "ES256")
    jwks_cache_seconds: float = 600.0
    leeway_seconds: float = 30.0


# Provider presets --------------------------------------------------------


def okta_config(
    domain: str,
    audience: str | None = None,
    *,
    authorization_server_id: str = "default",
) -> OIDCProviderConfig:
    """Okta customer-identity or workforce-identity tenant preset.

    Args:
        domain: Your Okta domain, e.g. `dev-12345.okta.com`.
        audience: Expected token audience. If your access tokens were
            issued for a specific resource server, pass that identifier.
        authorization_server_id: Okta authorization-server ID; "default"
            is Okta's built-in server.
    """
    return OIDCProviderConfig(
        discovery_url=(
            f"https://{domain}/oauth2/{authorization_server_id}"
            "/.well-known/openid-configuration"
        ),
        audience=audience,
    )


def auth0_config(domain: str, audience: str | None = None) -> OIDCProviderConfig:
    """Auth0 tenant preset.

    Args:
        domain: Your Auth0 domain, e.g. `acme.auth0.com`.
        audience: Your API audience (the `audience` param you pass when
            requesting tokens).
    """
    return OIDCProviderConfig(
        discovery_url=f"https://{domain}/.well-known/openid-configuration",
        audience=audience,
    )


def azure_ad_config(
    tenant_id: str,
    audience: str | None = None,
    *,
    v2: bool = True,
) -> OIDCProviderConfig:
    """Azure AD / Microsoft Entra preset.

    Args:
        tenant_id: Your Entra tenant UUID or verified domain.
        audience: The application (client) ID or API URI that tokens
            are issued for.
        v2: Use the v2.0 endpoints (recommended). v1.0 tokens have
            slightly different claim names.
    """
    version = "v2.0" if v2 else ""
    path = (f"https://login.microsoftonline.com/{tenant_id}/"
            + (f"{version}/" if version else "")
            + ".well-known/openid-configuration")
    return OIDCProviderConfig(
        discovery_url=path,
        audience=audience,
    )


# -- Verifier ---------------------------------------------------------------


class OIDCVerifier:
    """Verifies OIDC access or ID tokens using the provider's JWKS.

    Thread-safe. Caches JWKS responses and periodically refreshes.

    Requires: pip install iaiso[oidc] (for PyJWT with cryptography extra)
    """

    def __init__(
        self,
        config: OIDCProviderConfig,
        *,
        http_fetcher: Callable[[str], bytes] | None = None,
    ) -> None:
        try:
            import jwt  # noqa: F401
        except ImportError as e:  # pragma: no cover
            raise ImportError(
                "OIDCVerifier requires PyJWT + cryptography. "
                "Install with: pip install iaiso[oidc]"
            ) from e
        self._cfg = config
        self._fetch = http_fetcher or self._default_fetcher
        self._lock = threading.RLock()
        self._jwks: dict[str, Any] | None = None
        self._jwks_fetched_at = 0.0
        self._resolved_jwks_url: str | None = None
        self._resolved_issuer: str | None = None

    @staticmethod
    def _default_fetcher(url: str) -> bytes:
        try:
            with urllib.request.urlopen(url, timeout=5.0) as resp:
                return resp.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            raise OIDCNetworkError(f"Failed to fetch {url}: {exc}") from exc

    def _discover(self) -> None:
        """Resolve JWKS URL and issuer via the provider's discovery doc."""
        if self._cfg.jwks_url:
            self._resolved_jwks_url = self._cfg.jwks_url
            self._resolved_issuer = self._cfg.issuer
            return
        if not self._cfg.discovery_url:
            raise OIDCError(
                "OIDCProviderConfig needs either jwks_url or discovery_url"
            )
        doc = json.loads(self._fetch(self._cfg.discovery_url))
        if "jwks_uri" not in doc:
            raise OIDCError(
                f"Discovery doc missing jwks_uri: {self._cfg.discovery_url}"
            )
        self._resolved_jwks_url = doc["jwks_uri"]
        self._resolved_issuer = self._cfg.issuer or doc.get("issuer")

    def _ensure_jwks(self) -> dict[str, Any]:
        now = time.time()
        with self._lock:
            fresh = (
                self._jwks is not None
                and (now - self._jwks_fetched_at) < self._cfg.jwks_cache_seconds
            )
            if fresh:
                return self._jwks  # type: ignore[return-value]
            if self._resolved_jwks_url is None:
                self._discover()
            raw = self._fetch(self._resolved_jwks_url)  # type: ignore[arg-type]
            self._jwks = json.loads(raw)
            self._jwks_fetched_at = now
            return self._jwks

    def verify(self, token: str) -> dict[str, Any]:
        """Verify the token signature and claims; return claims dict.

        Raises OIDCError on any failure.
        """
        import jwt
        from jwt import PyJWKClient, PyJWKClientError

        jwks = self._ensure_jwks()

        # Find the right key by `kid` in the token header.
        try:
            header = jwt.get_unverified_header(token)
        except jwt.DecodeError as exc:
            raise OIDCError(f"Malformed token: {exc}") from exc
        kid = header.get("kid")
        if not kid:
            raise OIDCError("Token header missing 'kid'")
        key_obj = None
        for jwk in jwks.get("keys", []):
            if jwk.get("kid") == kid:
                key_obj = jwt.PyJWK(jwk).key
                break
        if key_obj is None:
            # Possible rotation — flush and retry once.
            with self._lock:
                self._jwks = None
            jwks = self._ensure_jwks()
            for jwk in jwks.get("keys", []):
                if jwk.get("kid") == kid:
                    key_obj = jwt.PyJWK(jwk).key
                    break
        if key_obj is None:
            raise OIDCError(f"No JWKS key matches kid={kid}")

        decode_kwargs: dict[str, Any] = {
            "algorithms": list(self._cfg.allowed_algorithms),
            "leeway": self._cfg.leeway_seconds,
        }
        if self._cfg.audience is not None:
            decode_kwargs["audience"] = self._cfg.audience
        if self._resolved_issuer is not None:
            decode_kwargs["issuer"] = self._resolved_issuer

        try:
            claims = jwt.decode(token, key=key_obj, **decode_kwargs)
        except jwt.ExpiredSignatureError as exc:
            raise OIDCError("Token expired") from exc
        except jwt.InvalidAudienceError as exc:
            raise OIDCError(f"Invalid audience: {exc}") from exc
        except jwt.InvalidIssuerError as exc:
            raise OIDCError(f"Invalid issuer: {exc}") from exc
        except jwt.InvalidTokenError as exc:
            raise OIDCError(f"Invalid token: {exc}") from exc
        return claims


# -- Scope mapping ----------------------------------------------------------


@dataclass
class ScopeMapping:
    """Rules for converting OIDC claims into IAIso scope strings.

    Attributes:
        scope_claims: Claim names whose values are space- or
            array-separated OAuth scopes to use directly. Common: `scp`
            (Azure AD), `scope` (Okta/Auth0 standard), `permissions`
            (Auth0 RBAC).
        group_claims: Claim names whose values are group memberships to
            translate into scopes. Common: `groups`, `roles`.
        group_to_scope: Map of group names to the IAIso scopes they
            grant. Groups not in this map are ignored.
        group_prefix: If not None, scopes derived from groups get this
            prefix. Example: `group_prefix="groups."` means membership
            in "engineers" becomes scope `groups.engineers`.
        include_raw_groups: If True, also emit scopes derived by
            applying `group_prefix` even if not in `group_to_scope`.
        subject_claim: Which claim to use as the subject. Defaults to
            `sub`; use `email` for user-facing audit log readability.
    """

    scope_claims: tuple[str, ...] = ("scp", "scope", "permissions")
    group_claims: tuple[str, ...] = ("groups", "roles")
    group_to_scope: dict[str, list[str]] = field(default_factory=dict)
    group_prefix: str | None = None
    include_raw_groups: bool = False
    subject_claim: str = "sub"


def derive_scopes(claims: dict[str, Any], mapping: ScopeMapping) -> list[str]:
    """Extract a list of IAIso scopes from verified OIDC claims."""
    scopes: set[str] = set()

    # Direct OAuth scopes — space-separated string, or list of strings.
    for claim in mapping.scope_claims:
        val = claims.get(claim)
        if val is None:
            continue
        if isinstance(val, str):
            scopes.update(s for s in val.split() if s)
        elif isinstance(val, list):
            scopes.update(str(s) for s in val)

    # Group-derived scopes.
    for claim in mapping.group_claims:
        val = claims.get(claim)
        if val is None:
            continue
        groups: list[str] = []
        if isinstance(val, str):
            groups = [val]
        elif isinstance(val, list):
            groups = [str(g) for g in val]

        for group in groups:
            # Explicit mapping
            mapped = mapping.group_to_scope.get(group)
            if mapped:
                scopes.update(mapped)
            # Raw groups as scopes
            if mapping.include_raw_groups and mapping.group_prefix is not None:
                scopes.add(f"{mapping.group_prefix}{group}")

    return sorted(scopes)


def enrich_from_oidc(
    token: str,
    *,
    verifier: OIDCVerifier,
    mapping: ScopeMapping | None = None,
) -> ConsentScope:
    """Verify an OIDC token and convert it directly to a ConsentScope.

    Useful when you want to gate an IAIso execution on an upstream OIDC
    access token without minting a separate IAIso consent token.

    Returns a ConsentScope. The `token` field holds the original OIDC
    token string. `execution_id` is None (not bound to a specific
    execution). `jti` uses the OIDC `jti` claim if present, else a
    content-derived fallback.

    If you need an IAIso-signed token, use `issue_from_oidc` instead.
    """
    mapping = mapping or ScopeMapping()
    claims = verifier.verify(token)
    subject = str(claims.get(mapping.subject_claim, claims.get("sub", "")))
    if not subject:
        raise OIDCError(f"No {mapping.subject_claim} claim in token")
    scopes = derive_scopes(claims, mapping)
    expires_at = float(claims["exp"]) if "exp" in claims else 0.0
    issued_at = float(claims.get("iat", time.time()))
    # OIDC `jti` is optional; fall back to a deterministic content hash so
    # revocation-by-jti still works.
    jti = str(claims.get("jti") or f"oidc:{hash((subject, issued_at)) & 0xffffffff:x}")
    return ConsentScope(
        token=token,
        subject=subject,
        scopes=list(scopes),
        execution_id=None,
        jti=jti,
        issued_at=issued_at,
        expires_at=expires_at,
        metadata={"oidc": {"iss": claims.get("iss"),
                           "aud": claims.get("aud")}},
    )


def issue_from_oidc(
    token: str,
    *,
    verifier: OIDCVerifier,
    issuer: ConsentIssuer,
    mapping: ScopeMapping | None = None,
    ttl_seconds: float | None = None,
) -> Any:
    """Verify an OIDC token, then mint a signed IAIso consent token.

    This is the preferred flow for production: you get a short-lived
    IAIso token with the scopes you derived, and the rest of the
    pipeline is independent of the IdP after issuance.
    """
    scope = enrich_from_oidc(token, verifier=verifier, mapping=mapping)
    return issuer.issue(
        subject=scope.subject,
        scopes=scope.scopes,
        ttl_seconds=ttl_seconds if ttl_seconds is not None else 3600.0,
    )
