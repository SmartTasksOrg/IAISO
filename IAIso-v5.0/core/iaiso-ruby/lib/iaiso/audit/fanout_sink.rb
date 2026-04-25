# frozen_string_literal: true

module IAIso
  module Audit
    # Broadcasts events to multiple sinks. Errors in any one sink do
    # not poison the others.
    class FanoutSink
      def initialize(*sinks)
        @sinks = sinks.flatten.freeze
      end

      def emit(event)
        @sinks.each do |s|
          begin
            s.emit(event)
          rescue StandardError
            # swallow
          end
        end
      end
    end
  end
end
