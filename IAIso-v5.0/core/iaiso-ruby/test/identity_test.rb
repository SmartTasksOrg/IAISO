# frozen_string_literal: true

require_relative "test_helper"
require "iaiso/identity"
require "iaiso/consent"
require "json"
require "base64"
require "openssl"

class IdentityTest < Minitest::Test
  def test_derive_direct_claim_string
    out = IAIso::Identity::OidcVerifier.derive_scopes(
      { "scope" => "tools.search tools.fetch" },
      IAIso::Identity::ScopeMapping.defaults,
    )
    assert_includes out, "tools.search"
    assert_includes out, "tools.fetch"
  end

  def test_derive_direct_claim_array
    out = IAIso::Identity::OidcVerifier.derive_scopes(
      { "scp" => ["a.b", "c"] },
      IAIso::Identity::ScopeMapping.defaults,
    )
    assert_equal ["a.b", "c"], out
  end

  def test_derive_group_to_scopes
    out = IAIso::Identity::OidcVerifier.derive_scopes(
      { "groups" => ["engineers"] },
      IAIso::Identity::ScopeMapping.new(group_to_scopes: { "engineers" => ["tools.search", "tools.fetch"] }),
    )
    assert_includes out, "tools.search"
    assert_includes out, "tools.fetch"
  end

  def test_always_grant_added
    out = IAIso::Identity::OidcVerifier.derive_scopes({}, IAIso::Identity::ScopeMapping.new(always_grant: ["base"]))
    assert_equal ["base"], out
  end

  def test_presets_have_expected_endpoints
    okta = IAIso::Identity::ProviderConfig.okta(domain: "acme.okta.com", audience: "api")
    assert_includes okta.discovery_url, "acme.okta.com"

    auth0 = IAIso::Identity::ProviderConfig.auth0(domain: "acme.auth0.com", audience: "api")
    assert auth0.issuer.end_with?("/")

    azure = IAIso::Identity::ProviderConfig.azure_ad(tenant: "tenant-id", audience: "api", v2: true)
    assert_includes azure.discovery_url, "v2.0"
  end

  def test_verify_fails_when_jwks_not_loaded
    v = IAIso::Identity::OidcVerifier.new(config: IAIso::Identity::ProviderConfig.defaults)
    assert_raises(IAIso::Identity::IdentityError) { v.verify("a.b.c") }
  end

  def test_rsa_verify_roundtrip
    priv = OpenSSL::PKey::RSA.generate(2048)
    n = priv.n.to_s(2)
    e = priv.e.to_s(2)
    kid = "test-key"
    header_json = JSON.generate({ "alg" => "RS256", "typ" => "JWT", "kid" => kid })
    claims = { "iss" => "https://test", "sub" => "user-1", "aud" => "myapi",
               "exp" => Time.now.to_i + 3600, "iat" => Time.now.to_i }
    claims_json = JSON.generate(claims)
    h = Base64.urlsafe_encode64(header_json, padding: false)
    c = Base64.urlsafe_encode64(claims_json, padding: false)
    sig = priv.sign(OpenSSL::Digest.new("SHA256"), "#{h}.#{c}")
    token = "#{h}.#{c}.#{Base64.urlsafe_encode64(sig, padding: false)}"

    jwks = JSON.generate({
      "keys" => [{
        "kty" => "RSA", "kid" => kid, "alg" => "RS256", "use" => "sig",
        "n" => Base64.urlsafe_encode64(n, padding: false),
        "e" => Base64.urlsafe_encode64(e, padding: false),
      }],
    })

    cfg = IAIso::Identity::ProviderConfig.new(
      issuer: "https://test", audience: "myapi",
      allowed_algorithms: ["RS256"], leeway_seconds: 5,
    )
    v = IAIso::Identity::OidcVerifier.new(config: cfg)
    v.set_jwks_from_bytes(jwks)
    verified = v.verify(token)
    assert_equal "user-1", verified["sub"]
  end
end
