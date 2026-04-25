# frozen_string_literal: true

require "securerandom"
require_relative "../audit/event"
require_relative "../audit/null_sink"
require_relative "pressure_config"
require_relative "pressure_engine"

module IAIso
  module Core
    # High-level execution facade. Composes a PressureEngine with an
    # audit sink and lifecycle management.
    #
    # Use BoundedExecution.run with a block for automatic cleanup, or
    # BoundedExecution.start + manual #close for explicit control.
    class BoundedExecution
      attr_reader :engine

      def initialize(execution_id: nil, config: PressureConfig.defaults,
                     audit_sink: nil, clock: nil, timestamp_clock: nil)
        execution_id = "exec-#{SecureRandom.hex(6)}" if execution_id.nil? || execution_id.empty?
        @audit_sink = audit_sink || Audit::NullSink.instance
        @ts_clock = timestamp_clock || clock || WallClock.instance
        @engine = PressureEngine.new(
          config: config,
          options: EngineOptions.new(
            execution_id: execution_id,
            audit_sink: @audit_sink,
            clock: clock || WallClock.instance,
            timestamp_clock: @ts_clock,
          ),
        )
        @closed = false
        @lock = Monitor.new
      end

      # Construct + return a started execution. The caller MUST #close it.
      def self.start(**opts)
        new(**opts)
      end

      # Run a block inside a bounded execution; closes on exit.
      def self.run(**opts)
        exec = new(**opts)
        errored = false
        begin
          yield exec
        rescue StandardError
          errored = true
          raise
        ensure
          exec.send(:close_with, errored: errored)
        end
      end

      def execution_id = @engine.execution_id
      def snapshot     = @engine.snapshot

      def record_tokens(tokens, tag: nil)
        @engine.step(StepInput.build(tokens: tokens, tag: tag))
      end

      def record_tool_call(name, tokens: 0)
        @engine.step(StepInput.build(tokens: tokens, tool_calls: 1, tag: name))
      end

      def record_step(work)
        @engine.step(work)
      end

      # Pre-check the engine state without advancing it.
      def check
        case @engine.lifecycle
        when Lifecycle::LOCKED then StepOutcome::LOCKED
        when Lifecycle::ESCALATED then StepOutcome::ESCALATED
        else StepOutcome::OK
        end
      end

      def reset = @engine.reset

      # Close the execution, emitting execution.closed. Idempotent.
      def close
        close_with(errored: false)
      end

      private

      def close_with(errored:)
        @lock.synchronize do
          return if @closed
          @closed = true
        end
        snap = @engine.snapshot
        @audit_sink.emit(Audit::Event.new(
          execution_id: @engine.execution_id,
          kind: "execution.closed",
          timestamp: @ts_clock.now,
          data: {
            "final_pressure" => snap.pressure,
            "final_lifecycle" => snap.lifecycle,
            "exception" => errored ? "error" : nil,
          },
        ))
      end
    end
  end
end
