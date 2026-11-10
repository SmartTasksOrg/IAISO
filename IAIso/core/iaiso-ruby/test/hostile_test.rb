# frozen_string_literal: true

require_relative "test_helper"
require "json"

# spec/pressure/hostile.json is shared by every IAIso port.
class HostileVectorsTest < Minitest::Test
  HOSTILE = JSON.parse(File.read(File.expand_path("../spec/pressure/hostile.json", __dir__)))

  def engine
    clk = IAIso::Core::ScriptedClock.new([0.0])
    IAIso::Core::PressureEngine.new(
      config: IAIso::Core::PressureConfig.defaults,
      options: IAIso::Core::EngineOptions.new(execution_id: "hostile",
                                              audit_sink: IAIso::Audit::MemorySink.new,
                                              clock: clk, timestamp_clock: clk)
    )
  end

  HOSTILE["reject"].each do |v|
    define_method("test_refuses_#{v['name']}") do
      assert_raises(ArgumentError) do
        engine.step(IAIso::Core::StepInput.from_hash(v["field"] => v["value"]))
      end
    end
  end

  def test_extreme_values_are_handled
    HOSTILE["accept"].each do |v|
      e = engine
      out = e.step(IAIso::Core::StepInput.from_hash(v["step"]))
      refute e.pressure.nan?, v["name"]
      assert_in_delta v["expect"]["pressure"], e.pressure, 1e-9, v["name"]
      assert_equal v["expect"]["outcome"], out.to_s, v["name"]
      assert_equal v["expect"]["lifecycle"], e.lifecycle.to_s, v["name"]
    end
  end

  def test_unknown_field_refused
    assert_raises(ArgumentError) { IAIso::Core::StepInput.from_hash("token" => 1) }
  end
end
