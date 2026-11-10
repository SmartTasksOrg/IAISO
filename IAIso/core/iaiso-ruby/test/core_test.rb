# frozen_string_literal: true

require_relative "test_helper"
require "iaiso/audit"
require "iaiso/core"

class CoreTest < Minitest::Test
  def test_enum_wire_values
    assert_equal "init",      IAIso::Core::Lifecycle::INIT
    assert_equal "running",   IAIso::Core::Lifecycle::RUNNING
    assert_equal "escalated", IAIso::Core::Lifecycle::ESCALATED
    assert_equal "released",  IAIso::Core::Lifecycle::RELEASED
    assert_equal "locked",    IAIso::Core::Lifecycle::LOCKED
    assert_equal "ok",        IAIso::Core::StepOutcome::OK
  end

  def test_config_rejects_bad_thresholds
    cfg = IAIso::Core::PressureConfig.new(escalation_threshold: 0.9, release_threshold: 0.5)
    assert_raises(IAIso::Core::ConfigError) { cfg.validate! }
  end

  def test_config_rejects_negative_coefficient
    cfg = IAIso::Core::PressureConfig.new(token_coefficient: -1.0)
    assert_raises(IAIso::Core::ConfigError) { cfg.validate! }
  end

  def test_engine_escalates_on_high_pressure
    sink = IAIso::Audit::MemorySink.new
    clk = IAIso::Core::ScriptedClock.new([0.0, 1.0])
    cfg = IAIso::Core::PressureConfig.new(
      escalation_threshold: 0.5, release_threshold: 0.95,
      dissipation_per_step: 0.0, depth_coefficient: 0.6,
    )
    eng = IAIso::Core::PressureEngine.new(
      config: cfg,
      options: IAIso::Core::EngineOptions.new(execution_id: "e", audit_sink: sink, clock: clk, timestamp_clock: clk),
    )
    outcome = eng.step(IAIso::Core::StepInput.build(depth: 1))
    assert_equal IAIso::Core::StepOutcome::ESCALATED, outcome
    assert_in_delta 0.6, eng.pressure, 1e-9
  end

  def test_engine_locks_after_release
    clk = IAIso::Core::ScriptedClock.new([0.0, 1.0, 2.0])
    cfg = IAIso::Core::PressureConfig.new(
      escalation_threshold: 0.5, release_threshold: 0.9,
      dissipation_per_step: 0.0, depth_coefficient: 1.0, post_release_lock: true,
    )
    eng = IAIso::Core::PressureEngine.new(
      config: cfg,
      options: IAIso::Core::EngineOptions.new(execution_id: "e"),
    )
    eng.step(IAIso::Core::StepInput.build(depth: 1))
    assert_equal IAIso::Core::Lifecycle::LOCKED, eng.lifecycle
    nxt = eng.step(IAIso::Core::StepInput.build(depth: 1))
    assert_equal IAIso::Core::StepOutcome::LOCKED, nxt
  end

  def test_engine_reset_emits_reset_event
    sink = IAIso::Audit::MemorySink.new
    clk = IAIso::Core::ScriptedClock.new([0.0, 1.0, 2.0])
    eng = IAIso::Core::PressureEngine.new(
      config: IAIso::Core::PressureConfig.defaults,
      options: IAIso::Core::EngineOptions.new(execution_id: "e", audit_sink: sink, clock: clk, timestamp_clock: clk),
    )
    eng.step(IAIso::Core::StepInput.build(tokens: 100))
    eng.reset
    kinds = sink.events.map(&:kind)
    assert_includes kinds, "engine.reset"
    assert_equal 0.0, eng.pressure
    assert_equal IAIso::Core::Lifecycle::INIT, eng.lifecycle
  end

  def test_bounded_execution_run_emits_closed
    sink = IAIso::Audit::MemorySink.new
    IAIso::Core::BoundedExecution.run(audit_sink: sink) do |exec|
      exec.record_tokens(100, tag: "x")
    end
    kinds = sink.events.map(&:kind)
    assert_includes kinds, "execution.closed"
  end

  def test_bounded_execution_auto_id_when_empty
    sink = IAIso::Audit::MemorySink.new
    IAIso::Core::BoundedExecution.run(audit_sink: sink) { |_e| }
    refute_empty sink.events
    assert sink.events.first.execution_id.start_with?("exec-")
  end

  def test_record_tool_call_advances
    exec = IAIso::Core::BoundedExecution.start
    out = exec.record_tool_call("search", tokens: 100)
    assert_equal IAIso::Core::StepOutcome::OK, out
    assert exec.snapshot.pressure > 0.0
    exec.close
  end
end
