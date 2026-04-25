# frozen_string_literal: true

require "json"
require_relative "result"
require_relative "../audit/null_sink"
require_relative "../core/pressure_config"
require_relative "../core/pressure_engine"
require_relative "../core/clock"

module IAIso
  module Conformance
    module PressureRunner
      TOLERANCE = 1e-9

      module_function

      def run(spec_root)
        path = File.join(spec_root, "pressure", "vectors.json")
        doc = ::JSON.parse(File.read(path))
        doc["vectors"].map { |v| run_one(v) }
      end

      def run_one(v)
        name = v["name"] || "?"

        # Build PressureConfig with overrides from vector.
        kw = {}
        if v["config"].is_a?(Hash)
          c = v["config"]
          %w[escalation_threshold release_threshold dissipation_per_step
             dissipation_per_second token_coefficient tool_coefficient
             depth_coefficient].each do |f|
            kw[f.to_sym] = c[f].to_f if c.key?(f) && c[f].is_a?(Numeric)
          end
          kw[:post_release_lock] = c["post_release_lock"] if [true, false].include?(c["post_release_lock"])
        end

        cfg = IAIso::Core::PressureConfig.new(**kw)
        clock_seq = (v["clock"].is_a?(Array) ? v["clock"] : [0.0]).map(&:to_f)
        clk = IAIso::Core::ScriptedClock.new(clock_seq)

        expect_err = v["expect_config_error"]
        engine = nil
        begin
          engine = IAIso::Core::PressureEngine.new(
            config: cfg,
            options: IAIso::Core::EngineOptions.new(
              execution_id: "vec-#{name}",
              audit_sink: IAIso::Audit::NullSink.instance,
              clock: clk, timestamp_clock: clk,
            ),
          )
        rescue IAIso::Core::ConfigError => e
          if expect_err.nil?
            return VectorResult.fail("pressure", name, "engine init failed: #{e.message}")
          end
          unless e.message.include?(expect_err)
            return VectorResult.fail("pressure", name, "expected error containing '#{expect_err}', got: #{e.message}")
          end
          return VectorResult.pass("pressure", name)
        end
        if expect_err
          return VectorResult.fail("pressure", name, "expected config error containing '#{expect_err}', got Ok")
        end

        # initial state check
        if v["expected_initial"].is_a?(Hash)
          init = v["expected_initial"]
          snap = engine.snapshot
          if (snap.pressure - init["pressure"].to_f).abs > TOLERANCE
            return VectorResult.fail("pressure", name, "initial pressure: got #{snap.pressure}, want #{init["pressure"]}")
          end
          if snap.step != init["step"].to_i
            return VectorResult.fail("pressure", name, "initial step: got #{snap.step}, want #{init["step"]}")
          end
          if snap.lifecycle != init["lifecycle"]
            return VectorResult.fail("pressure", name, "initial lifecycle: got #{snap.lifecycle}, want #{init["lifecycle"]}")
          end
          if (snap.last_step_at - init["last_step_at"].to_f).abs > TOLERANCE
            return VectorResult.fail("pressure", name, "initial last_step_at: got #{snap.last_step_at}, want #{init["last_step_at"]}")
          end
        end

        # steps
        steps = v["steps"] || []
        exp_steps = v["expected_steps"] || []
        steps.each_with_index do |step, i|
          if step["reset"]
            engine.reset
            outcome = "ok"
          else
            kw = {}
            kw[:tokens] = step["tokens"].to_i if step.key?("tokens")
            kw[:tool_calls] = step["tool_calls"].to_i if step.key?("tool_calls")
            kw[:depth] = step["depth"].to_i if step.key?("depth")
            kw[:tag] = step["tag"] if step.key?("tag")
            outcome = engine.step(IAIso::Core::StepInput.build(**kw))
          end
          exp = exp_steps[i]
          unless exp
            return VectorResult.fail("pressure", name, "step #{i}: no expected entry")
          end
          if outcome != exp["outcome"]
            return VectorResult.fail("pressure", name, "step #{i}: outcome got #{outcome}, want #{exp["outcome"]}")
          end
          snap = engine.snapshot
          if (snap.pressure - exp["pressure"].to_f).abs > TOLERANCE
            return VectorResult.fail("pressure", name, "step #{i}: pressure got #{snap.pressure}, want #{exp["pressure"]}")
          end
          if snap.step != exp["step"].to_i
            return VectorResult.fail("pressure", name, "step #{i}: step got #{snap.step}, want #{exp["step"]}")
          end
          if snap.lifecycle != exp["lifecycle"]
            return VectorResult.fail("pressure", name, "step #{i}: lifecycle got #{snap.lifecycle}, want #{exp["lifecycle"]}")
          end
        end
        VectorResult.pass("pressure", name)
      end
    end
  end
end
