# frozen_string_literal: true

module IAIso
  module Middleware
    class MiddlewareError < StandardError; end

    class EscalationRaisedError < MiddlewareError
      def initialize(message = "execution escalated; raise-on-escalation enabled")
        super
      end
    end

    class LockedError < MiddlewareError
      def initialize(message = "execution locked")
        super
      end
    end

    class ProviderError < MiddlewareError
      def initialize(message)
        super("provider error: #{message}")
      end
    end
  end
end
