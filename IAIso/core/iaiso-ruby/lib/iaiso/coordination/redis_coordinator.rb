# frozen_string_literal: true

require_relative "shared_pressure_coordinator"

module IAIso
  module Coordination
    # Structural Redis client interface. Implement around redis-rb,
    # hiredis-client, or any Redis library to plug it into RedisCoordinator.
    #
    # Required methods:
    #   #eval(script, keys:, args:) -> reply
    #   #hset(key, pairs)            -> unit (pairs is array of [field, value])
    #   #hkeys(key)                  -> array of field names
    module RedisClient
      # Documentation only — duck-typed.
    end

    # Redis-backed coordinator. Interoperable with the Python, Node, Go,
    # Rust, Java, C#, PHP, and Swift references via the shared keyspace
    # and the verbatim Lua script in UPDATE_AND_FETCH_SCRIPT.
    class RedisCoordinator
      # The normative Lua script — verbatim from
      # spec/coordinator/README.md §1.2. Bytes are identical across all
      # nine reference SDKs to guarantee fleet coordination.
      UPDATE_AND_FETCH_SCRIPT = <<~LUA
        \nlocal pressures_key = KEYS[1]
        local exec_id       = ARGV[1]
        local new_pressure  = ARGV[2]
        local ttl_seconds   = tonumber(ARGV[3])

        redis.call('HSET', pressures_key, exec_id, new_pressure)
        if ttl_seconds > 0 then
          redis.call('EXPIRE', pressures_key, ttl_seconds)
        end

        return redis.call('HGETALL', pressures_key)
      LUA

      def initialize(redis:, coordinator_id: "default",
                     escalation_threshold: 5.0, release_threshold: 8.0,
                     notify_cooldown_seconds: 1.0,
                     key_prefix: "iaiso:coord", pressures_ttl_seconds: 300,
                     aggregator: nil, audit_sink: nil,
                     on_escalation: nil, on_release: nil, clock: nil)
        @redis = redis
        @key_prefix = key_prefix
        @pressures_ttl_seconds = pressures_ttl_seconds.to_i
        agg = aggregator || IAIso::Policy::SumAggregator.new
        @clock = clock || IAIso::Core::WallClock.instance
        @audit_sink = audit_sink || IAIso::Audit::NullSink.instance
        # Shadow coordinator handles in-process lifecycle; we drive it
        # from external Redis state.
        @shadow = SharedPressureCoordinator.new(
          coordinator_id: coordinator_id,
          escalation_threshold: escalation_threshold,
          release_threshold: release_threshold,
          notify_cooldown_seconds: notify_cooldown_seconds,
          aggregator: agg,
          audit_sink: IAIso::Audit::NullSink.instance,
          on_escalation: on_escalation,
          on_release: on_release,
          clock: @clock,
          emit_init: false,
        )
        @audit_sink.emit(IAIso::Audit::Event.new(
          execution_id: "coord:#{coordinator_id}",
          kind: "coordinator.init",
          timestamp: @clock.now,
          data: {
            "coordinator_id" => coordinator_id,
            "aggregator" => agg.name,
            "backend" => "redis",
          },
        ))
      end

      def register(execution_id)
        @redis.hset(pressures_key, [[execution_id.to_s, "0.0"]])
        @shadow.register(execution_id)
      end

      def unregister(execution_id)
        @redis.eval(
          "redis.call('HDEL', KEYS[1], ARGV[1]); return 1",
          keys: [pressures_key],
          args: [execution_id.to_s],
        )
        @shadow.unregister(execution_id)
      end

      def update(execution_id, pressure)
        if pressure < 0.0 || pressure > 1.0
          raise CoordinatorError, "pressure must be in [0, 1], got #{pressure}"
        end
        reply = @redis.eval(
          UPDATE_AND_FETCH_SCRIPT,
          keys: [pressures_key],
          args: [execution_id.to_s, pressure.to_s, @pressures_ttl_seconds.to_s],
        )
        updated = self.class.parse_hgetall_flat(reply)
        @shadow.set_pressures_from_map(updated)
        @shadow.evaluate
      end

      def reset
        keys = @redis.hkeys(pressures_key)
        unless keys.empty?
          pairs = keys.map { |k| [k.to_s, "0.0"] }
          @redis.hset(pressures_key, pairs)
        end
        @shadow.reset
      end

      def snapshot = @shadow.snapshot

      # Parse a flat HGETALL Redis reply into a name→float map.
      # Accepts either a flat array (standard redis-rb response) or a hash.
      def self.parse_hgetall_flat(reply)
        out = {}
        return out if reply.nil?
        if reply.is_a?(Hash)
          reply.each { |k, v| out[k.to_s] = v.to_f }
          return out
        end
        if reply.is_a?(Array)
          (0...reply.size).step(2) do |i|
            break if i + 1 >= reply.size
            out[reply[i].to_s] = reply[i + 1].to_f
          end
        end
        out
      end

      private

      def pressures_key
        "#{@key_prefix}:#{@shadow.coordinator_id}:pressures"
      end
    end
  end
end
