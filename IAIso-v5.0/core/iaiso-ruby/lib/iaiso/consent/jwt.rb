# frozen_string_literal: true

require "openssl"
require "base64"
require "json"
require_relative "errors"
require_relative "algorithm"

module IAIso
  module Consent
    # Internal JWT codec. Hand-rolled HS256/RS256 using OpenSSL stdlib.
    # No third-party JWT library required.
    module JWT
      module_function

      # Sign claims into a compact JWT.
      #
      # @param algorithm [String] Algorithm::HS256 or Algorithm::RS256
      # @param claims [Hash] insertion order is preserved (Ruby 1.9+)
      # @param hs_key [String, nil] raw HMAC bytes (HS256)
      # @param rs_private_key [String, nil] PEM-encoded RSA private key (RS256)
      def sign(algorithm:, claims:, hs_key: nil, rs_private_key: nil)
        header = { "alg" => algorithm, "typ" => "JWT" }
        header_json = canonical_json(header)
        # Ruby preserves Hash insertion order, so JSON.generate preserves
        # the spec-mandated claim order.
        claims_json = canonical_json(claims)
        header_b64 = b64url_encode(header_json)
        claims_b64 = b64url_encode(claims_json)
        signing_input = "#{header_b64}.#{claims_b64}"
        signature =
          case algorithm
          when Algorithm::HS256
            raise InvalidTokenError, "HS256 requires hs_key" if hs_key.nil? || hs_key.empty?
            OpenSSL::HMAC.digest("sha256", hs_key, signing_input)
          when Algorithm::RS256
            raise InvalidTokenError, "RS256 requires rs_private_key" if rs_private_key.nil?
            key = rs_private_key.is_a?(OpenSSL::PKey::RSA) ? rs_private_key : OpenSSL::PKey::RSA.new(rs_private_key)
            key.sign(OpenSSL::Digest.new("SHA256"), signing_input)
          else
            raise InvalidTokenError, "unsupported algorithm: #{algorithm}"
          end
        "#{signing_input}.#{b64url_encode(signature)}"
      end

      # Parse a compact JWT into its three parts. Does NOT verify the signature.
      def parse(token)
        parts = token.split(".", -1)
        unless parts.size == 3
          raise InvalidTokenError, "malformed JWT: expected 3 segments"
        end
        header_b64, claims_b64, sig_b64 = parts
        header = ::JSON.parse(b64url_decode(header_b64))
        claims = ::JSON.parse(b64url_decode(claims_b64))
        signature = b64url_decode(sig_b64)
        unless header.is_a?(Hash) && claims.is_a?(Hash)
          raise InvalidTokenError, "JWT header/claims must be objects"
        end
        {
          header_b64: header_b64,
          claims_b64: claims_b64,
          signature_b64: sig_b64,
          header: header,
          claims: claims,
          signature: signature,
        }
      rescue ::JSON::ParserError => e
        raise InvalidTokenError, "malformed JWT JSON: #{e.message}"
      end

      # Verify the signature on a parsed JWT.
      def verify_signature(parsed, algorithm:, hs_key: nil, rs_public_key: nil)
        signing_input = "#{parsed[:header_b64]}.#{parsed[:claims_b64]}"
        case algorithm
        when Algorithm::HS256
          return false if hs_key.nil?
          expected = OpenSSL::HMAC.digest("sha256", hs_key, signing_input)
          # constant-time compare via OpenSSL.fixed_length_secure_compare
          return false unless expected.bytesize == parsed[:signature].bytesize
          OpenSSL.fixed_length_secure_compare(expected, parsed[:signature])
        when Algorithm::RS256
          return false if rs_public_key.nil?
          key = rs_public_key.is_a?(OpenSSL::PKey::RSA) ? rs_public_key : OpenSSL::PKey::RSA.new(rs_public_key)
          key.verify(OpenSSL::Digest.new("SHA256"), parsed[:signature], signing_input)
        else
          false
        end
      end

      # Encode a Hash to JSON, preserving insertion order (Ruby 1.9+).
      # We don't escape forward slashes — matches the other reference SDKs.
      def canonical_json(value)
        ::JSON.generate(value, ascii_only: false)
      end

      def b64url_encode(bytes)
        Base64.urlsafe_encode64(bytes, padding: false)
      end

      def b64url_decode(str)
        # Ruby's urlsafe_decode64 is strict about padding; pad before decoding.
        padded = str.dup
        rem = padded.length % 4
        padded << ("=" * (4 - rem)) if rem.positive?
        Base64.urlsafe_decode64(padded)
      rescue ArgumentError => e
        raise InvalidTokenError, "malformed base64url segment: #{e.message}"
      end
    end
  end
end
