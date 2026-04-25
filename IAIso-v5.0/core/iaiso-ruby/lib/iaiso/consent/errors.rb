# frozen_string_literal: true

module IAIso
  module Consent
    # Base class for all consent failures.
    class ConsentError < StandardError; end

    # Token failed structural or signature validation.
    class InvalidTokenError < ConsentError; end

    # Token's exp + leeway has passed.
    class ExpiredTokenError < ConsentError
      def initialize(message = "token expired")
        super
      end
    end

    # Token's jti is on a revocation list.
    class RevokedTokenError < ConsentError
      attr_reader :jti

      def initialize(jti)
        @jti = jti
        super("token revoked: #{jti}")
      end
    end

    # Verified scope set is missing a required scope.
    class InsufficientScopeError < ConsentError
      attr_reader :required, :granted

      def initialize(required, granted)
        @required = required
        @granted = granted
        super("scope '#{required}' not granted; have [#{granted.join(", ")}]")
      end
    end
  end
end
