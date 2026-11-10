# frozen_string_literal: true

require "monitor"
require "set"

module IAIso
  module Consent
    # Thread-safe set of revoked JTIs.
    class RevocationList
      include MonitorMixin

      def initialize
        super
        @set = Set.new
      end

      def revoke(jti)
        synchronize { @set << jti }
      end

      def revoked?(jti)
        synchronize { @set.include?(jti) }
      end

      def clear
        synchronize { @set.clear }
      end
    end
  end
end
