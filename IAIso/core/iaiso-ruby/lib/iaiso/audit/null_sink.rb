# frozen_string_literal: true

module IAIso
  module Audit
    # Discards events.
    class NullSink
      INSTANCE = new.freeze

      def emit(_event); end

      def self.instance = INSTANCE
    end
  end
end
