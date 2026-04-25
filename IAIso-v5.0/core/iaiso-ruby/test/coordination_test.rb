# frozen_string_literal: true

require_relative "test_helper"
require "iaiso/audit"
require "iaiso/coordination"
require "iaiso/policy"

class CoordinationTest < Minitest::Test
  def test_aggregates_sum
    c = IAIso::Coordination::SharedPressureCoordinator.new(
      audit_sink: IAIso::Audit::MemorySink.new,
    )
    c.register("a")
    c.register("b")
    c.update("a", 0.3)
    snap = c.update("b", 0.5)
    assert_in_delta 0.8, snap.aggregate_pressure, 1e-9
  end

  def test_escalation_callback_fires
    calls = 0
    c = IAIso::Coordination::SharedPressureCoordinator.new(
      escalation_threshold: 0.7, release_threshold: 0.95,
      notify_cooldown_seconds: 0.0,
      on_escalation: ->(_s) { calls += 1 },
    )
    c.register("a")
    c.update("a", 0.8)
    assert_equal 1, calls
  end

  def test_rejects_bad_pressure
    c = IAIso::Coordination::SharedPressureCoordinator.new
    assert_raises(IAIso::Coordination::CoordinatorError) { c.update("a", 1.5) }
  end

  def test_lua_script_unchanged_from_spec
    s = IAIso::Coordination::RedisCoordinator::UPDATE_AND_FETCH_SCRIPT
    assert_includes s, "pressures_key = KEYS[1]"
    assert_includes s, "HGETALL"
    assert_includes s, "EXPIRE"
  end

  def test_parse_hgetall_flat
    reply = ["a", "0.3", "b", "0.5"]
    out = IAIso::Coordination::RedisCoordinator.parse_hgetall_flat(reply)
    assert_in_delta 0.3, out["a"], 1e-9
    assert_in_delta 0.5, out["b"], 1e-9
  end

  def test_redis_coordinator_with_mock
    mock = MockRedis.new
    c = IAIso::Coordination::RedisCoordinator.new(
      redis: mock, coordinator_id: "test",
      escalation_threshold: 0.7, release_threshold: 0.9,
      pressures_ttl_seconds: 300,
      audit_sink: IAIso::Audit::MemorySink.new,
    )
    c.register("a")
    c.register("b")
    c.update("a", 0.4)
    snap = c.update("b", 0.3)
    assert_in_delta 0.7, snap.aggregate_pressure, 1e-9
  end

  # Minimal in-memory mock for testing
  class MockRedis
    def initialize
      @hashes = {}
    end

    def eval(script, keys:, args:)
      key = keys[0]
      @hashes[key] ||= {}
      if script.include?("HSET") && script.include?("HGETALL")
        @hashes[key][args[0]] = args[1]
        flat = []
        @hashes[key].each { |k, v| flat << k << v }
        return flat
      end
      if script.include?("HDEL")
        @hashes[key].delete(args[0])
        return 1
      end
      nil
    end

    def hset(key, pairs)
      @hashes[key] ||= {}
      pairs.each { |p| @hashes[key][p[0]] = p[1] }
    end

    def hkeys(key)
      (@hashes[key] || {}).keys
    end
  end
end
