# frozen_string_literal: true

require "json"
require_relative "result"
require_relative "../consent"

module IAIso
  module Conformance
    module ConsentRunner
      module_function

      def run(spec_root)
        path = File.join(spec_root, "consent", "vectors.json")
        doc = ::JSON.parse(File.read(path))
        shared_key = doc["hs256_key_shared"]
        out = []
        (doc["scope_match"] || []).each { |v| out << run_scope_match(v) }
        (doc["scope_match_errors"] || []).each { |v| out << run_scope_match_error(v) }
        (doc["valid_tokens"] || []).each { |v| out << run_valid_token(shared_key, v) }
        (doc["invalid_tokens"] || []).each { |v| out << run_invalid_token(shared_key, v) }
        (doc["issue_and_verify_roundtrip"] || []).each { |v| out << run_roundtrip(shared_key, v) }
        out
      end

      def parse_alg(v)
        v["algorithm"] || IAIso::Consent::Algorithm::HS256
      end

      def run_scope_match(v)
        name = "scope_match/#{v["name"]}"
        got = IAIso::Consent::Scopes.granted(v["granted"], v["requested"])
        want = v["expected"]
        return VectorResult.fail("consent", name, "got #{got}, want #{want}") if got != want
        VectorResult.pass("consent", name)
      rescue => e
        VectorResult.fail("consent", name, "unexpected exception: #{e.message}")
      end

      def run_scope_match_error(v)
        name = "scope_match_errors/#{v["name"]}"
        expect = v["expect_error"]
        IAIso::Consent::Scopes.granted(v["granted"], v["requested"])
        VectorResult.fail("consent", name, "expected error containing '#{expect}', got Ok")
      rescue ArgumentError => e
        unless e.message.downcase.include?(expect.downcase)
          return VectorResult.fail("consent", name, "expected '#{expect}', got: #{e.message}")
        end
        VectorResult.pass("consent", name)
      end

      def run_valid_token(shared_key, v)
        name = "valid_tokens/#{v["name"]}"
        now = v["now"].to_i
        issuer = v["issuer"] || "iaiso"
        alg = parse_alg(v)
        verifier = IAIso::Consent::Verifier.new(
          algorithm: alg, issuer: issuer, hs_key: shared_key,
          clock: ->{ now },
        )
        scope = verifier.verify(v["token"])
        exp = v["expected"]
        return VectorResult.fail("consent", name, "sub: got #{scope.subject}, want #{exp["sub"]}") if scope.subject != exp["sub"]
        return VectorResult.fail("consent", name, "jti: got #{scope.jti}, want #{exp["jti"]}") if scope.jti != exp["jti"]
        if scope.scopes != exp["scopes"]
          return VectorResult.fail("consent", name, "scopes mismatch: got #{scope.scopes}, want #{exp["scopes"]}")
        end
        want_exec = exp["execution_id"]
        if scope.execution_id != want_exec
          return VectorResult.fail("consent", name, "execution_id: got #{scope.execution_id.inspect}, want #{want_exec.inspect}")
        end
        VectorResult.pass("consent", name)
      rescue => e
        VectorResult.fail("consent", name, "verify failed: #{e.message}")
      end

      def run_invalid_token(shared_key, v)
        name = "invalid_tokens/#{v["name"]}"
        now = v["now"].to_i
        issuer = v["issuer"] || "iaiso"
        alg = parse_alg(v)
        exec_id = v["execution_id"]
        expect = v["expect_error"]
        verifier = IAIso::Consent::Verifier.new(
          algorithm: alg, issuer: issuer, hs_key: shared_key,
          clock: ->{ now },
        )
        verifier.verify(v["token"], requested_execution_id: exec_id)
        VectorResult.fail("consent", name, "expected error '#{expect}', got Ok")
      rescue IAIso::Consent::ExpiredTokenError
        return VectorResult.fail("consent", name, "expected '#{expect}', got expired") if expect != "expired"
        VectorResult.pass("consent", name)
      rescue IAIso::Consent::RevokedTokenError
        return VectorResult.fail("consent", name, "expected '#{expect}', got revoked") if expect != "revoked"
        VectorResult.pass("consent", name)
      rescue IAIso::Consent::InvalidTokenError => e
        return VectorResult.fail("consent", name, "expected '#{expect}', got invalid: #{e.message}") if expect != "invalid"
        VectorResult.pass("consent", name)
      rescue => e
        VectorResult.fail("consent", name, "unexpected: #{e.class}: #{e.message}")
      end

      def run_roundtrip(shared_key, v)
        name = "roundtrip/#{v["name"]}"
        issue = v["issue"]
        ttl = (issue["ttl_seconds"] || 3600).to_i
        subject = issue["subject"]
        scopes = issue["scopes"]
        exec_id = issue["execution_id"]
        metadata = issue["metadata"]
        now = (v["now"] || 1_700_000_000).to_i
        issuer = v["issuer"] || "iaiso"
        alg = parse_alg(v)

        is = IAIso::Consent::Issuer.new(
          algorithm: alg, issuer: issuer, hs_key: shared_key,
          clock: ->{ now },
        )
        scope = is.issue(
          subject: subject, scopes: scopes, execution_id: exec_id,
          ttl_seconds: ttl, metadata: metadata,
        )

        expect_success = !!v["expected_after_verify_succeeds"]
        verify_exec = v["verify_with_execution_id"]
        ver = IAIso::Consent::Verifier.new(
          algorithm: alg, issuer: issuer, hs_key: shared_key,
          clock: ->{ now + 1 },
        )
        begin
          verified = ver.verify(scope.token, requested_execution_id: verify_exec)
        rescue => e
          return expect_success ?
            VectorResult.fail("consent", name, "expected verify to succeed, failed: #{e.message}") :
            VectorResult.pass("consent", name)
        end
        return VectorResult.fail("consent", name, "expected verify to fail, succeeded") unless expect_success
        return VectorResult.fail("consent", name, "subject mismatch") if verified.subject != subject
        return VectorResult.fail("consent", name, "scopes mismatch") if verified.scopes != scopes
        VectorResult.pass("consent", name)
      end
    end
  end
end
