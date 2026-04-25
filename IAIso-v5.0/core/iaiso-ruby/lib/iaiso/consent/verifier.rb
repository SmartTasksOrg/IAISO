# frozen_string_literal: true

require_relative "algorithm"
require_relative "errors"
require_relative "jwt"
require_relative "scope"

module IAIso
  module Consent
    # Verifies signed consent tokens.
    class Verifier
      attr_reader :algorithm, :issuer, :leeway_seconds

      def initialize(algorithm: Algorithm::HS256, issuer: "iaiso",
                     hs_key: nil, rs_public_key: nil,
                     revocation_list: nil, leeway_seconds: 5, clock: nil)
        @algorithm = algorithm
        @issuer = issuer
        @hs_key = hs_key
        @rs_public_key = rs_public_key
        @revocation_list = revocation_list
        @leeway_seconds = leeway_seconds.to_i
        @clock = clock || ->{ Time.now.to_i }
      end

      # Verify `token`. If `requested_execution_id` is non-nil and the
      # token is bound to a different execution, raises InvalidTokenError.
      def verify(token, requested_execution_id: nil)
        parsed = JWT.parse(token)

        alg = parsed[:header]["alg"]
        unless alg == @algorithm
          raise InvalidTokenError, "unexpected algorithm: #{alg.inspect}"
        end

        ok = JWT.verify_signature(
          parsed,
          algorithm: @algorithm,
          hs_key: @hs_key,
          rs_public_key: @rs_public_key,
        )
        raise InvalidTokenError, "signature verification failed" unless ok

        claims = parsed[:claims]
        %w[exp iat iss sub jti].each do |k|
          unless claims.key?(k)
            raise InvalidTokenError, "missing required claim: #{k}"
          end
        end

        unless claims["iss"] == @issuer
          raise InvalidTokenError, "iss mismatch: got #{claims["iss"].inspect}, want #{@issuer.inspect}"
        end

        exp = claims["exp"].to_i
        now = @clock.call.to_i
        if exp + @leeway_seconds < now
          raise ExpiredTokenError
        end

        jti = claims["jti"].to_s
        if @revocation_list && @revocation_list.revoked?(jti)
          raise RevokedTokenError, jti
        end

        token_exec = claims["execution_id"]
        if requested_execution_id && token_exec && token_exec != requested_execution_id
          raise InvalidTokenError,
                "token bound to #{token_exec.inspect}, requested #{requested_execution_id.inspect}"
        end

        scopes = (claims["scopes"] || []).map(&:to_s)
        metadata = claims["metadata"].is_a?(Hash) ? claims["metadata"] : {}

        Scope.new(
          token: token,
          subject: claims["sub"].to_s,
          scopes: scopes,
          execution_id: token_exec,
          jti: jti,
          issued_at: claims["iat"].to_i,
          expires_at: exp,
          metadata: metadata,
        )
      end
    end
  end
end
