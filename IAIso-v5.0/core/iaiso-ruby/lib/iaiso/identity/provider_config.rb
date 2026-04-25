# frozen_string_literal: true

module IAIso
  module Identity
    # Configuration for an OidcVerifier.
    class ProviderConfig
      attr_reader :discovery_url, :jwks_url, :issuer, :audience,
                  :allowed_algorithms, :leeway_seconds

      def initialize(discovery_url: nil, jwks_url: nil, issuer: nil, audience: nil,
                     allowed_algorithms: ["RS256"], leeway_seconds: 5)
        @discovery_url = discovery_url
        @jwks_url = jwks_url
        @issuer = issuer
        @audience = audience
        @allowed_algorithms = allowed_algorithms.map(&:to_s).freeze
        @leeway_seconds = leeway_seconds.to_i
        freeze
      end

      def self.defaults = new

      def self.okta(domain:, audience:)
        new(
          discovery_url: "https://#{domain}/.well-known/openid-configuration",
          issuer: "https://#{domain}",
          audience: audience,
        )
      end

      def self.auth0(domain:, audience:)
        new(
          discovery_url: "https://#{domain}/.well-known/openid-configuration",
          issuer: "https://#{domain}/",
          audience: audience,
        )
      end

      def self.azure_ad(tenant:, audience:, v2: true)
        base = v2 ? "https://login.microsoftonline.com/#{tenant}/v2.0"
                  : "https://login.microsoftonline.com/#{tenant}"
        new(
          discovery_url: "#{base}/.well-known/openid-configuration",
          issuer: base,
          audience: audience,
        )
      end
    end
  end
end
