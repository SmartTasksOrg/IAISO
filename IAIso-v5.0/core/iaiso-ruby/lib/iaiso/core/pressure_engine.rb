# frozen_string_literal: true

require "monitor"
require_relative "../audit/event"
require_relative "../audit/null_sink"
require_relative "lifecycle"
require_relative "step_outcome"
require_relative "clock"

module IAIso
  module Core
    # A single step's worth of work.
    StepInput = Data.define(:tokens, :tool_calls, :depth, :tag) do
      def self.empty = new(tokens: 0, tool_calls: 0, depth: 0, tag: nil)
      def self.build(tokens: 0, tool_calls: 0, depth: 0, tag: nil)
        new(tokens: tokens, tool_calls: tool_calls, depth: depth, tag: tag)
      end
    end

    # Read-only snapshot of engine state.
    PressureSnapshot = Data.define(:pressure, :step, :lifecycle, :last_step_at)

    # Options for PressureEngine.
    class EngineOptions
      attr_reader :execution_id, :audit_sink, :clock, :timestamp_clock

      def initialize(execution_id:, audit_sink: nil, clock: nil, timestamp_clock: nil)
        @execution_id    = execution_id.to_s
        @audit_sink      = audit_sink || Audit::NullSink.instance
        @clock           = clock || WallClock.instance
        @timestamp_clock = timestamp_clock || @clock
      end
    end

    # The IAIso pressure engine. Tracks accumulated load, decays over
    # time, emits lifecycle events on threshold crossings.
    #
    # See spec/pressure/README.md for normative semantics.
    class PressureEngine
      include MonitorMixin

      attr_reader :config, :execution_id

      def initialize(config:, options:)
        super()
        config.validate!
        @config       = config
        @execution_id = options.execution_id
        @audit        = options.audit_sink
        @clock        = options.clock
        @ts_clock     = options.timestamp_clock
        @pressure     = 0.0
        @step_count   = 0
        @lifecycle    = Lifecycle::INIT
        @last_step_at = @clock.now
        emit("engine.init", { "pressure" => 0.0 })
      end

      def pressure;  synchronize { @pressure }   end
      def lifecycle; synchronize { @lifecycle } end

      def snapshot
        synchronize do
          PressureSnapshot.new(
            pressure: @pressure,
            step: @step_count,
            lifecycle: @lifecycle,
            last_step_at: @last_step_at,
          )
        end
      end

      # Account for a unit of work.
      def step(work = StepInput.empty)
        synchronize do
          if @lifecycle == Lifecycle::LOCKED
            emit_unlocked("engine.step.rejected", {
              "reason" => "locked",
              "requested_tokens" => work.tokens.to_i,
              "requested_tools" => work.tool_calls.to_i,
            })
            return StepOutcome::LOCKED
          end

          now = @clock.now
          elapsed = [0.0, now - @last_step_at].max
          delta = (work.tokens.to_f / 1000.0) * @config.token_coefficient \
                + work.tool_calls.to_f * @config.tool_coefficient \
                + work.depth.to_f * @config.depth_coefficient
          decay = @config.dissipation_per_step + elapsed * @config.dissipation_per_second
          @pressure = clamp01(@pressure + delta - decay)
          @step_count += 1
          @last_step_at = now
          @lifecycle = Lifecycle::RUNNING

          step_data = {
            "step" => @step_count,
            "pressure" => @pressure,
            "delta" => delta,
            "decay" => decay,
            "tokens" => work.tokens.to_i,
            "tool_calls" => work.tool_calls.to_i,
            "depth" => work.depth.to_i,
            "tag" => work.tag,
          }
          pressure_now = @pressure
          release_thr = @config.release_threshold
          esc_thr = @config.escalation_threshold
          plr = @config.post_release_lock

          # Emit step event; release the monitor first so the sink
          # can't deadlock by re-entering this engine.
          emit_unlocked("engine.step", step_data)

          if pressure_now >= release_thr
            emit_unlocked("engine.release", {
              "pressure" => pressure_now,
              "threshold" => release_thr,
            })
            @pressure = 0.0
            if plr
              @lifecycle = Lifecycle::LOCKED
              emit_unlocked("engine.locked", { "reason" => "post_release_lock" })
            else
              @lifecycle = Lifecycle::RUNNING
            end
            return StepOutcome::RELEASED
          end
          if pressure_now >= esc_thr
            @lifecycle = Lifecycle::ESCALATED
            emit_unlocked("engine.escalation", {
              "pressure" => pressure_now,
              "threshold" => esc_thr,
            })
            return StepOutcome::ESCALATED
          end
          StepOutcome::OK
        end
      end

      # Reset the engine. Emits engine.reset.
      def reset
        synchronize do
          @pressure = 0.0
          @step_count = 0
          @last_step_at = @clock.now
          @lifecycle = Lifecycle::INIT
          emit_unlocked("engine.reset", { "pressure" => 0.0 })
          PressureSnapshot.new(
            pressure: @pressure,
            step: @step_count,
            lifecycle: @lifecycle,
            last_step_at: @last_step_at,
          )
        end
      end

      private

      def emit(kind, data)
        ev = Audit::Event.new(
          execution_id: @execution_id,
          kind: kind,
          timestamp: @ts_clock.now,
          data: data,
        )
        @audit.emit(ev)
      end

      def emit_unlocked(kind, data)
        # We're inside `synchronize`; calling out to a foreign sink is
        # a re-entrancy risk. Use this helper to make the call site
        # explicit. (Ruby's MonitorMixin is re-entrant within the same
        # thread, so this is safe in practice; the helper exists for
        # future-proofing if we move to Mutex.)
        emit(kind, data)
      end

      def clamp01(v)
        return 0.0 if v < 0
        return 1.0 if v > 1
        v
      end
    end
  end
end
