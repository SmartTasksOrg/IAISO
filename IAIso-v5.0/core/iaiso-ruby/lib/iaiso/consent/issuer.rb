# frozen_string_literal: true

require "securerandom"
require "base64"
require_relative "algorithm"
require_relative "jwt"
require_relative "scope"

module IAIso
  module Consent
    # Issues consent tokens.
    class Issuer
      attr_reader :algorithm, :issuer, :default_ttl_seconds

      def initialize(algorithm: Algorithm::HS256, issuer: "iaiso",
                     hs_key: nil, rs_private_key: nil,
                     default_ttl_seconds: 3600, clock: nil)
        @algorithm = algorithm
        @issuer = issuer
        @hs_key = hs_key
        @rs_private_key = rs_private_key
        @default_ttl_seconds = default_ttl_seconds.to_i
        @clock = clock || ->{ Time.now.to_i }
      end

      # Issue a fresh token. Spec field order: iss, sub, iat, exp, jti,
      # scopes, [execution_id], [metadata]. Ruby Hash preserves insertion
      # order, so this order is emitted exactly.
      def issue(subject:, scopes:, execution_id: nil, ttl_seconds: nil, metadata: nil)
        now = @clock.call.to_i
        ttl = (ttl_seconds || @default_ttl_seconds).to_i
        exp = now + ttl
        jti = SecureRandom.hex(16)

        claims = {
          "iss" => @issuer,
          "sub" => subject,
          "iat" => now,
          "exp" => exp,
          "jti" => jti,
          "scopes" => scopes,
        }
        claims["execution_id"] = execution_id unless execution_id.nil?
        claims["metadata"] = metadata if metadata && !metadata.empty?

        token = JWT.sign(
          algorithm: @algorithm, claims: claims,
          hs_key: @hs_key, rs_private_key: @rs_private_key,
        )

        Scope.new(
          token: token,
          subject: subject,
          scopes: scopes,
          execution_id: execution_id,
          jti: jti,
          issued_at: now,
          expires_at: exp,
          metadata: metadata || {},
        )
      end

      # Generate a 64-byte base64url-no-pad HS256 secret.
      def self.generate_hs256_secret
        Base64.urlsafe_encode64(SecureRandom.bytes(64), padding: false)
      end
    end
  end
end
