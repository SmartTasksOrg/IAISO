# frozen_string_literal: true

module IAIso
  module Policy
    # Coordinator-section configuration.
    class CoordinatorConfig
      attr_reader :escalation_threshold, :release_threshold, :notify_cooldown_seconds

      def initialize(escalation_threshold: 5.0, release_threshold: 8.0,
                     notify_cooldown_seconds: 1.0)
        @escalation_threshold = escalation_threshold.to_f
        @release_threshold = release_threshold.to_f
        @notify_cooldown_seconds = notify_cooldown_seconds.to_f
        freeze
      end

      def self.defaults = new
    end

    # Consent-section configuration.
    class ConsentPolicy
      attr_reader :issuer, :default_ttl_seconds, :required_scopes, :allowed_algorithms

      def initialize(issuer: nil, default_ttl_seconds: 3600.0,
                     required_scopes: [], allowed_algorithms: ["HS256", "RS256"])
        @issuer = issuer
        @default_ttl_seconds = default_ttl_seconds.to_f
        @required_scopes = required_scopes.map(&:to_s).freeze
        @allowed_algorithms = allowed_algorithms.map(&:to_s).freeze
        freeze
      end

      def self.defaults = new
    end

    # Assembled, validated policy document.
    class Policy
      attr_reader :version, :pressure, :coordinator, :consent, :aggregator, :metadata

      def initialize(version:, pressure:, coordinator:, consent:, aggregator:, metadata: {})
        @version = version
        @pressure = pressure
        @coordinator = coordinator
        @consent = consent
        @aggregator = aggregator
        @metadata = metadata || {}
        freeze
      end
    end
  end
end
