# frozen_string_literal: true

require "monitor"

module IAIso
  module Audit
    # Appends events as JSONL to a file.
    # I/O errors are silently dropped — sinks must not propagate them.
    class JSONLFileSink
      include MonitorMixin

      def initialize(path)
        super()
        @path = path
      end

      def emit(event)
        line = event.to_json + "\n"
        synchronize do
          File.open(@path, "a:UTF-8") { |f| f.write(line) }
        rescue StandardError
          # swallow
        end
      end
    end
  end
end
