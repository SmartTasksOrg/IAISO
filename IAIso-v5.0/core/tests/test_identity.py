"""Tests for OIDC identity integration.

We use cryptography to generate a real RSA keypair, PyJWT to sign a
token with it, and publish the public half via a fake JWKS endpoint
(an HTTP fetcher that returns canned bytes). This exercises the real
verification path end-to-end without needing a live IdP.
"""

from __future__ import annotations

import base64
import json
import time
import uuid
from typing import Any

import pytest

# PyJWT + cryptography are required for the module; skip if missing.
pytest.importorskip("jwt")
pytest.importorskip("cryptography")

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import jwt

from iaiso import ConsentIssuer
from iaiso.identity import (
    OIDCError,
    OIDCProviderConfig,
    OIDCVerifier,
    ScopeMapping,
    auth0_config,
    azure_ad_config,
    derive_scopes,
    enrich_from_oidc,
    issue_from_oidc,
    okta_config,
)


# -- JWKS fixture -----------------------------------------------------------


def _b64url(n: int) -> str:
    """Base64url-encode an integer for JWKS n/e fields."""
    b = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


@pytest.fixture
def rsa_keypair() -> dict[str, Any]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_numbers = private_key.public_key().public_numbers()
    kid = str(uuid.uuid4())
    jwk = {
        "kty": "RSA",
        "kid": kid,
        "use": "sig",
        "alg": "RS256",
        "n": _b64url(public_numbers.n),
        "e": _b64url(public_numbers.e),
    }
    jwks = {"keys": [jwk]}
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return {
        "kid": kid,
        "jwks": jwks,
        "private_pem": pem,
        "private_key": private_key,
    }


def _make_token(kp: dict[str, Any], **claims: Any) -> str:
    defaults: dict[str, Any] = {
        "iss": "https://issuer.test",
        "aud": "my-api",
        "sub": "user-1",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }
    defaults.update(claims)
    return jwt.encode(
        defaults, kp["private_pem"], algorithm="RS256",
        headers={"kid": kp["kid"]},
    )


def _fake_fetcher(responses: dict[str, bytes]):
    def fetch(url: str) -> bytes:
        if url not in responses:
            raise FileNotFoundError(f"Unmocked URL: {url}")
        return responses[url]
    return fetch


# -- OIDCVerifier tests -----------------------------------------------------


def test_verify_valid_token(rsa_keypair: dict[str, Any]) -> None:
    token = _make_token(rsa_keypair)
    discovery = json.dumps({
        "issuer": "https://issuer.test",
        "jwks_uri": "https://issuer.test/jwks",
    }).encode()
    fetch = _fake_fetcher({
        "https://issuer.test/.well-known/openid-configuration": discovery,
        "https://issuer.test/jwks": json.dumps(rsa_keypair["jwks"]).encode(),
    })
    verifier = OIDCVerifier(
        OIDCProviderConfig(
            discovery_url="https://issuer.test/.well-known/openid-configuration",
            audience="my-api",
        ),
        http_fetcher=fetch,
    )
    claims = verifier.verify(token)
    assert claims["sub"] == "user-1"


def test_verify_wrong_audience(rsa_keypair: dict[str, Any]) -> None:
    token = _make_token(rsa_keypair, aud="someone-else")
    discovery = json.dumps({
        "issuer": "https://issuer.test",
        "jwks_uri": "https://issuer.test/jwks",
    }).encode()
    fetch = _fake_fetcher({
        "https://issuer.test/.well-known/openid-configuration": discovery,
        "https://issuer.test/jwks": json.dumps(rsa_keypair["jwks"]).encode(),
    })
    verifier = OIDCVerifier(
        OIDCProviderConfig(
            discovery_url="https://issuer.test/.well-known/openid-configuration",
            audience="my-api",
        ),
        http_fetcher=fetch,
    )
    with pytest.raises(OIDCError, match="audience"):
        verifier.verify(token)


def test_verify_expired_token(rsa_keypair: dict[str, Any]) -> None:
    token = _make_token(rsa_keypair, exp=int(time.time()) - 100)
    fetch = _fake_fetcher({
        "https://issuer.test/jwks": json.dumps(rsa_keypair["jwks"]).encode(),
    })
    verifier = OIDCVerifier(
        OIDCProviderConfig(
            jwks_url="https://issuer.test/jwks",
            issuer="https://issuer.test",
            audience="my-api",
        ),
        http_fetcher=fetch,
    )
    with pytest.raises(OIDCError, match="expired"):
        verifier.verify(token)


def test_verify_unknown_kid(rsa_keypair: dict[str, Any]) -> None:
    # Sign with the real key but advertise a bogus kid
    token = jwt.encode(
        {"sub": "x", "iat": int(time.time()),
         "exp": int(time.time()) + 60, "iss": "https://issuer.test"},
        rsa_keypair["private_pem"],
        algorithm="RS256",
        headers={"kid": "nonexistent"},
    )
    fetch = _fake_fetcher({
        "https://issuer.test/jwks": json.dumps(rsa_keypair["jwks"]).encode(),
    })
    verifier = OIDCVerifier(
        OIDCProviderConfig(
            jwks_url="https://issuer.test/jwks",
            issuer="https://issuer.test",
        ),
        http_fetcher=fetch,
    )
    with pytest.raises(OIDCError, match="kid"):
        verifier.verify(token)


def test_jwks_caching(rsa_keypair: dict[str, Any]) -> None:
    """JWKS should be cached — multiple verifications shouldn't refetch."""
    fetch_count = {"n": 0}

    def counting_fetch(url: str) -> bytes:
        fetch_count["n"] += 1
        return json.dumps(rsa_keypair["jwks"]).encode()

    verifier = OIDCVerifier(
        OIDCProviderConfig(
            jwks_url="https://issuer.test/jwks",
            issuer="https://issuer.test",
        ),
        http_fetcher=counting_fetch,
    )
    for _ in range(3):
        verifier.verify(_make_token(rsa_keypair, aud=None))
    assert fetch_count["n"] == 1


# -- Scope mapping ----------------------------------------------------------


def test_derive_scopes_from_scp_claim() -> None:
    claims = {"scp": "read.docs write.docs admin.users"}
    scopes = derive_scopes(claims, ScopeMapping())
    assert sorted(scopes) == ["admin.users", "read.docs", "write.docs"]


def test_derive_scopes_from_permissions_list() -> None:
    claims = {"permissions": ["read:books", "write:books"]}
    scopes = derive_scopes(claims, ScopeMapping())
    assert sorted(scopes) == ["read:books", "write:books"]


def test_derive_scopes_from_groups_via_mapping() -> None:
    mapping = ScopeMapping(
        group_to_scope={
            "engineers": ["tools.deploy", "tools.rollback"],
            "admins": ["admin.all"],
        },
    )
    claims = {"groups": ["engineers", "contractors"]}
    scopes = derive_scopes(claims, mapping)
    # "contractors" not in mapping → ignored
    assert sorted(scopes) == ["tools.deploy", "tools.rollback"]


def test_derive_scopes_include_raw_groups() -> None:
    mapping = ScopeMapping(
        group_prefix="groups.",
        include_raw_groups=True,
    )
    claims = {"groups": ["eng", "ops"]}
    scopes = derive_scopes(claims, mapping)
    assert sorted(scopes) == ["groups.eng", "groups.ops"]


def test_derive_scopes_combines_sources() -> None:
    mapping = ScopeMapping(
        group_to_scope={"eng": ["tools.build"]},
    )
    claims = {"scp": "read.public", "groups": ["eng"]}
    scopes = derive_scopes(claims, mapping)
    assert sorted(scopes) == ["read.public", "tools.build"]


# -- Full enrichment flow ---------------------------------------------------


def test_enrich_from_oidc(rsa_keypair: dict[str, Any]) -> None:
    token = _make_token(
        rsa_keypair,
        sub="alice@example.com",
        scp="read.docs",
        groups=["engineers"],
    )
    fetch = _fake_fetcher({
        "https://issuer.test/jwks": json.dumps(rsa_keypair["jwks"]).encode(),
    })
    verifier = OIDCVerifier(
        OIDCProviderConfig(
            jwks_url="https://issuer.test/jwks",
            issuer="https://issuer.test",
            audience="my-api",
        ),
        http_fetcher=fetch,
    )
    mapping = ScopeMapping(
        group_to_scope={"engineers": ["tools.deploy"]},
        subject_claim="sub",
    )
    scope = enrich_from_oidc(token, verifier=verifier, mapping=mapping)
    assert scope.subject == "alice@example.com"
    assert set(scope.scopes) == {"read.docs", "tools.deploy"}


def test_issue_from_oidc(rsa_keypair: dict[str, Any]) -> None:
    token = _make_token(
        rsa_keypair, sub="bob", scp="admin.all",
    )
    fetch = _fake_fetcher({
        "https://issuer.test/jwks": json.dumps(rsa_keypair["jwks"]).encode(),
    })
    verifier = OIDCVerifier(
        OIDCProviderConfig(
            jwks_url="https://issuer.test/jwks",
            issuer="https://issuer.test",
            audience="my-api",
        ),
        http_fetcher=fetch,
    )
    iaiso_issuer = ConsentIssuer(
        signing_key=b"x" * 32, issuer="iaiso-local",
    )
    consent_token = issue_from_oidc(
        token, verifier=verifier, issuer=iaiso_issuer, ttl_seconds=300,
    )
    assert consent_token.token.count(".") == 2  # JWT format
    # The minted token should verify against a matching ConsentVerifier
    from iaiso import ConsentVerifier
    cv = ConsentVerifier(verification_key=b"x" * 32, issuer="iaiso-local")
    verified = cv.verify(consent_token.token)
    assert verified.subject == "bob"
    assert "admin.all" in verified.scopes


# -- Provider presets (smoke tests) -----------------------------------------


def test_okta_preset_builds_discovery_url() -> None:
    cfg = okta_config("dev-123.okta.com", audience="api://my-api")
    assert "dev-123.okta.com" in cfg.discovery_url
    assert cfg.audience == "api://my-api"


def test_auth0_preset_builds_discovery_url() -> None:
    cfg = auth0_config("acme.auth0.com", audience="https://api.acme.com")
    assert "acme.auth0.com" in cfg.discovery_url


def test_azure_ad_preset_v2() -> None:
    cfg = azure_ad_config("tenant-uuid", audience="my-app")
    assert "v2.0" in cfg.discovery_url
    assert "login.microsoftonline.com" in cfg.discovery_url
