# frozen_string_literal: true

require "monitor"
require_relative "lifecycle"
require_relative "errors"
require_relative "snapshot"
require_relative "../audit/event"
require_relative "../audit/null_sink"
require_relative "../core/clock"
require_relative "../policy/aggregator"

module IAIso
  module Coordination
    # In-memory coordinator that aggregates pressure across a single
    # process's executions.
    class SharedPressureCoordinator
      include MonitorMixin

      attr_reader :coordinator_id, :aggregator

      def initialize(coordinator_id: "default",
                     escalation_threshold: 5.0, release_threshold: 8.0,
                     notify_cooldown_seconds: 1.0,
                     aggregator: nil, audit_sink: nil,
                     on_escalation: nil, on_release: nil,
                     clock: nil, emit_init: true)
        super()
        if release_threshold <= escalation_threshold
          raise CoordinatorError,
                "release_threshold must exceed escalation_threshold (#{release_threshold} <= #{escalation_threshold})"
        end
        @coordinator_id = coordinator_id
        @escalation_threshold = escalation_threshold.to_f
        @release_threshold = release_threshold.to_f
        @notify_cooldown_seconds = notify_cooldown_seconds.to_f
        @aggregator = aggregator || IAIso::Policy::SumAggregator.new
        @audit_sink = audit_sink || IAIso::Audit::NullSink.instance
        @on_escalation = on_escalation
        @on_release = on_release
        @clock = clock || IAIso::Core::WallClock.instance
        @pressures = {}
        @lifecycle = Lifecycle::NOMINAL
        @last_notify_at = 0.0
        if emit_init
          emit("coordinator.init", {
            "coordinator_id" => coordinator_id,
            "aggregator" => @aggregator.name,
            "backend" => "memory",
          })
        end
      end

      def register(execution_id)
        synchronize { @pressures[execution_id.to_s] = 0.0 }
        emit("coordinator.execution_registered", { "execution_id" => execution_id })
        snapshot
      end

      def unregister(execution_id)
        synchronize { @pressures.delete(execution_id.to_s) }
        emit("coordinator.execution_unregistered", { "execution_id" => execution_id })
        snapshot
      end

      def update(execution_id, pressure)
        if pressure < 0.0 || pressure > 1.0
          raise CoordinatorError, "pressure must be in [0, 1], got #{pressure}"
        end
        synchronize { @pressures[execution_id.to_s] = pressure.to_f }
        evaluate
      end

      def reset
        count = 0
        synchronize do
          count = @pressures.size
          @pressures.each_key { |k| @pressures[k] = 0.0 }
          @lifecycle = Lifecycle::NOMINAL
        end
        emit("coordinator.reset", { "fleet_size" => count })
        count
      end

      def snapshot
        synchronize do
          agg = @aggregator.aggregate(@pressures)
          sorted = @pressures.sort.to_h
          Snapshot.new(
            coordinator_id: @coordinator_id,
            aggregate_pressure: agg,
            lifecycle: @lifecycle,
            active_executions: sorted.size,
            per_execution: sorted,
          )
        end
      end

      # Used by RedisCoordinator to drive the lifecycle from external state.
      def set_pressures_from_map(updated)
        synchronize do
          @pressures = {}
          updated.each { |k, v| @pressures[k.to_s] = v.to_f }
        end
      end

      def evaluate
        snap_now = nil
        triggered = nil
        agg_value = nil
        synchronize do
          now = @clock.now
          agg = @aggregator.aggregate(@pressures)
          prior = @lifecycle
          in_cooldown = (now - @last_notify_at) < @notify_cooldown_seconds

          nxt =
            if agg >= @release_threshold
              Lifecycle::RELEASED
            elsif agg >= @escalation_threshold
              prior == Lifecycle::NOMINAL ? Lifecycle::ESCALATED : prior
            else
              Lifecycle::NOMINAL
            end
          @lifecycle = nxt
          agg_value = agg

          if nxt != prior && !in_cooldown
            @last_notify_at = now
            triggered = nxt
          end
        end

        snap_now = snapshot

        case triggered
        when Lifecycle::RELEASED
          emit("coordinator.release", {
            "aggregate_pressure" => agg_value,
            "threshold" => @release_threshold,
          })
          @on_release&.call(snap_now)
        when Lifecycle::ESCALATED
          emit("coordinator.escalation", {
            "aggregate_pressure" => agg_value,
            "threshold" => @escalation_threshold,
          })
          @on_escalation&.call(snap_now)
        when Lifecycle::NOMINAL
          emit("coordinator.returned_to_nominal", { "aggregate_pressure" => agg_value })
        end
        snap_now
      end

      private

      def emit(kind, data)
        @audit_sink.emit(IAIso::Audit::Event.new(
          execution_id: "coord:#{@coordinator_id}",
          kind: kind,
          timestamp: @clock.now,
          data: data,
        ))
      end
    end
  end
end
