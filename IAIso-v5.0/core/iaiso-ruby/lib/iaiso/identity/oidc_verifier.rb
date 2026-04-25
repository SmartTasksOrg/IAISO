# frozen_string_literal: true

require "json"
require "openssl"
require "base64"
require "monitor"
require_relative "errors"
require_relative "jwk"
require_relative "../consent/jwt"
require_relative "../consent/scope"

module IAIso
  module Identity
    # IAIso OIDC identity verifier.
    #
    # HTTP-free. The caller fetches JWKS bytes (using Net::HTTP, Faraday,
    # HTTParty — anything) and passes them to `set_jwks_from_bytes`.
    # This keeps the SDK dependency-light and lets users use whichever
    # HTTP client they prefer.
    class OidcVerifier
      include MonitorMixin

      attr_reader :config

      def initialize(config:, clock: nil)
        super()
        @config = config
        @jwks = nil
        @clock = clock || ->{ Time.now.to_i }
      end

      # Inject pre-fetched JWKS bytes into the verifier's cache.
      def set_jwks_from_bytes(body)
        root = ::JSON.parse(body)
      rescue ::JSON::ParserError => e
        raise IdentityError, "JWKS parse failed: #{e.message}"
      else
        unless root.is_a?(Hash) && root["keys"].is_a?(Array)
          raise IdentityError, "JWKS missing keys array"
        end
        keys = root["keys"].map do |k|
          k.is_a?(Hash) ? Jwk.from_hash(k) : nil
        end.compact
        synchronize { @jwks = Jwks.new(keys: keys) }
      end

      def verify(token)
        jwks = synchronize { @jwks }
        raise IdentityError, "oidc: JWKS not loaded; call set_jwks_from_bytes first" if jwks.nil?

        parsed = IAIso::Consent::JWT.parse(token)
        alg = parsed[:header]["alg"]
        unless @config.allowed_algorithms.include?(alg)
          raise IdentityError, "oidc: algorithm not allowed: #{alg}"
        end
        kid = parsed[:header]["kid"].to_s

        match = jwks.keys.find { |k| !k.kid.nil? && k.kid == kid }
        match ||= jwks.keys.first if jwks.keys.size == 1 && kid.empty?
        raise IdentityError, "oidc: kid #{kid} not found in JWKS" if match.nil?
        raise IdentityError, "oidc: unsupported key type: #{match.kty}" if match.kty != "RSA"

        # Build OpenSSL::PKey::RSA from JWK (n, e). Ruby's OpenSSL stdlib
        # handles this natively with PKey::RSA.new and a hash of components
        # OR by building an ASN.1 sequence. We use OpenSSL::PKey::RSA.new
        # via PEM construction since older Ruby OpenSSL doesn't accept the
        # hash form; ASN.1 SubjectPublicKeyInfo is straightforward.
        key = build_rsa_public_key(match.n, match.e)

        signing_input = "#{parsed[:header_b64]}.#{parsed[:claims_b64]}"
        ok = key.verify(OpenSSL::Digest.new("SHA256"), parsed[:signature], signing_input)
        raise IdentityError, "oidc: signature verification failed" unless ok

        claims = parsed[:claims]
        if @config.issuer && !@config.issuer.empty?
          unless claims["iss"] == @config.issuer
            raise IdentityError, "oidc: iss mismatch: got #{claims["iss"].inspect}, want #{@config.issuer.inspect}"
          end
        end

        if claims.key?("exp")
          exp = claims["exp"].to_i
          now = @clock.call.to_i
          raise IdentityError, "oidc: token expired" if exp + @config.leeway_seconds < now
        end

        if @config.audience && !@config.audience.empty?
          unless audience_matches?(claims["aud"], @config.audience)
            raise IdentityError, "oidc: aud mismatch (expected #{@config.audience.inspect})"
          end
        end
        claims
      end

      # Convert verified claims into a deduplicated list of IAIso scopes.
      def self.derive_scopes(claims, mapping)
        direct = mapping.direct_claims.empty? ? %w[scp scope permissions] : mapping.direct_claims
        seen = {}
        direct.each do |c|
          val = claims[c]
          next if val.nil?
          if val.is_a?(String)
            val.split(/[\s,]+/).each { |t| seen[t] = true unless t.empty? }
          elsif val.is_a?(Array)
            val.each { |t| seen[t.to_s] = true if t.is_a?(String) || t.is_a?(Symbol) }
          end
        end
        groups = []
        %w[groups roles].each do |c|
          val = claims[c]
          groups.concat(val.select { |g| g.is_a?(String) }) if val.is_a?(Array)
        end
        groups.each do |g|
          (mapping.group_to_scopes[g] || []).each { |s| seen[s] = true }
        end
        mapping.always_grant.each { |s| seen[s] = true }
        seen.keys
      end

      # Mint an IAIso consent scope from a verified OIDC identity.
      def self.issue_from_oidc(verifier:, issuer:, token:, mapping:,
                                ttl_seconds: 3600, execution_id: nil)
        claims = verifier.verify(token)
        subject = (claims["sub"] || "unknown").to_s
        scopes = derive_scopes(claims, mapping)
        metadata = {}
        { "iss" => "oidc_iss", "jti" => "oidc_jti", "aud" => "oidc_aud" }.each do |src, dst|
          metadata[dst] = claims[src] if claims.key?(src)
        end
        issuer.issue(
          subject: subject, scopes: scopes,
          execution_id: execution_id, ttl_seconds: ttl_seconds,
          metadata: metadata.empty? ? nil : metadata,
        )
      end

      private

      def audience_matches?(aud, want)
        return false if aud.nil?
        return aud == want if aud.is_a?(String)
        return aud.any? { |a| a == want } if aud.is_a?(Array)
        false
      end

      def build_rsa_public_key(n_b64, e_b64)
        # Decode JWK n, e from base64url to integer-bytes, then build
        # an OpenSSL::PKey::RSA via ASN.1 SubjectPublicKeyInfo. OpenSSL
        # stdlib parses this cleanly without us having to hand-roll DER.
        n_bytes = IAIso::Consent::JWT.b64url_decode(n_b64)
        e_bytes = IAIso::Consent::JWT.b64url_decode(e_b64)

        n_int = OpenSSL::BN.new(n_bytes, 2)
        e_int = OpenSSL::BN.new(e_bytes, 2)

        # Ruby 3.0+ OpenSSL bindings: build via ASN.1 encoding of an
        # RSAPublicKey, then wrap in SubjectPublicKeyInfo.
        rsa_pub = OpenSSL::ASN1::Sequence.new([
          OpenSSL::ASN1::Integer.new(n_int),
          OpenSSL::ASN1::Integer.new(e_int),
        ])
        spki = OpenSSL::ASN1::Sequence.new([
          OpenSSL::ASN1::Sequence.new([
            OpenSSL::ASN1::ObjectId.new("rsaEncryption"),
            OpenSSL::ASN1::Null.new(nil),
          ]),
          OpenSSL::ASN1::BitString.new(rsa_pub.to_der),
        ])
        OpenSSL::PKey::RSA.new(spki.to_der)
      end
    end
  end
end
