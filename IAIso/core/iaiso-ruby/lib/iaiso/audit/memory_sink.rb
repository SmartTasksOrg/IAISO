# frozen_string_literal: true

require "monitor"

module IAIso
  module Audit
    # Stores events in memory. Useful for tests.
    class MemorySink
      include MonitorMixin

      def initialize
        super
        @events = []
      end

      def emit(event)
        synchronize { @events << event }
      end

      def events
        synchronize { @events.dup }
      end

      def clear
        synchronize { @events.clear }
      end
    end
  end
end
