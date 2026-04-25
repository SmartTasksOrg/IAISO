# frozen_string_literal: true

module IAIso
  module Audit
    # Prints events as canonical JSON to standard output, one per line.
    class StdoutSink
      INSTANCE = new.freeze

      def emit(event)
        $stdout.puts(event.to_json)
      end

      def self.instance = INSTANCE
    end
  end
end
