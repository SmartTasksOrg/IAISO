# frozen_string_literal: true

require "monitor"

module IAIso
  module Core
    # Source of seconds-since-epoch as a Float. This is documentation;
    # any object responding to `now` works (Ruby duck typing).
    module Clock
      def now
        raise NotImplementedError
      end
    end

    # Real time via Time.now.
    class WallClock
      INSTANCE = new.freeze

      def now = Time.now.to_f

      def self.instance = INSTANCE
    end

    # Pre-recorded clock values; deterministic for tests.
    class ScriptedClock
      include MonitorMixin

      def initialize(sequence)
        super()
        @sequence = sequence.map(&:to_f)
        @idx = 0
      end

      def now
        synchronize do
          return 0.0 if @sequence.empty?
          v = @idx < @sequence.size ? @sequence[@idx] : @sequence.last
          @idx += 1 if @idx < @sequence.size
          v
        end
      end

      def reset
        synchronize { @idx = 0 }
      end
    end

    # Block-backed clock.
    class ClosureClock
      def initialize(&block)
        @block = block
      end

      def now = @block.call.to_f
    end
  end
end
