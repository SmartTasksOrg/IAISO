# frozen_string_literal: true

require_relative "test_helper"
require "iaiso/consent"

class ConsentTest < Minitest::Test
  SECRET = "test_secret_long_enough_for_hs256_security_xx"

  def test_scope_exact_match
    assert IAIso::Consent::Scopes.granted(["tools.search"], "tools.search")
  end

  def test_scope_prefix_at_boundary
    assert IAIso::Consent::Scopes.granted(["tools"], "tools.search")
  end

  def test_scope_substring_not_boundary
    refute IAIso::Consent::Scopes.granted(["tools"], "toolsbar")
  end

  def test_scope_more_specific_doesnt_satisfy
    refute IAIso::Consent::Scopes.granted(["tools.search.bulk"], "tools.search")
  end

  def test_empty_requested_raises
    assert_raises(ArgumentError) { IAIso::Consent::Scopes.granted(["tools"], "") }
  end

  def test_issue_verify_roundtrip
    issuer = IAIso::Consent::Issuer.new(
      algorithm: IAIso::Consent::Algorithm::HS256, issuer: "iaiso",
      hs_key: SECRET, clock: ->{ 1_700_000_000 },
    )
    scope = issuer.issue(subject: "user-1", scopes: ["tools.search", "tools.fetch"])
    refute_empty scope.token

    verifier = IAIso::Consent::Verifier.new(
      algorithm: IAIso::Consent::Algorithm::HS256, issuer: "iaiso",
      hs_key: SECRET, clock: ->{ 1_700_000_001 },
    )
    verified = verifier.verify(scope.token)
    assert_equal "user-1", verified.subject
    assert verified.grants?("tools.search")
  end

  def test_verify_rejects_expired
    issuer = IAIso::Consent::Issuer.new(hs_key: SECRET, clock: ->{ 1_700_000_000 })
    scope = issuer.issue(subject: "u", scopes: ["tools"], ttl_seconds: 1)
    verifier = IAIso::Consent::Verifier.new(hs_key: SECRET, clock: ->{ 1_700_000_010 })
    assert_raises(IAIso::Consent::ExpiredTokenError) { verifier.verify(scope.token) }
  end

  def test_verify_honors_revocation
    issuer = IAIso::Consent::Issuer.new(hs_key: SECRET, clock: ->{ 1_700_000_000 })
    scope = issuer.issue(subject: "u", scopes: ["tools"])
    rl = IAIso::Consent::RevocationList.new
    rl.revoke(scope.jti)
    verifier = IAIso::Consent::Verifier.new(
      hs_key: SECRET, revocation_list: rl, clock: ->{ 1_700_000_001 },
    )
    assert_raises(IAIso::Consent::RevokedTokenError) { verifier.verify(scope.token) }
  end

  def test_verify_honors_execution_binding
    issuer = IAIso::Consent::Issuer.new(hs_key: SECRET, clock: ->{ 1_700_000_000 })
    scope = issuer.issue(subject: "u", scopes: ["tools"], execution_id: "exec-abc")
    verifier = IAIso::Consent::Verifier.new(hs_key: SECRET, clock: ->{ 1_700_000_001 })
    assert_raises(IAIso::Consent::InvalidTokenError) do
      verifier.verify(scope.token, requested_execution_id: "exec-xyz")
    end
  end

  def test_verify_rejects_tampered_token
    issuer = IAIso::Consent::Issuer.new(hs_key: SECRET, clock: ->{ 1_700_000_000 })
    scope = issuer.issue(subject: "u", scopes: ["tools"])
    tampered = scope.token[0...-5] + "XXXXX"
    verifier = IAIso::Consent::Verifier.new(hs_key: SECRET, clock: ->{ 1_700_000_001 })
    assert_raises(IAIso::Consent::InvalidTokenError) { verifier.verify(tampered) }
  end

  def test_generate_hs256_secret_length
    s = IAIso::Consent::Issuer.generate_hs256_secret
    assert s.length >= 64
  end
end
