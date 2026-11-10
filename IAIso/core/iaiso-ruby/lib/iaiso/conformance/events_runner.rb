# frozen_string_literal: true

require "json"
require_relative "result"
require_relative "../audit/memory_sink"
require_relative "../core/pressure_config"
require_relative "../core/pressure_engine"
require_relative "../core/clock"

module IAIso
  module Conformance
    module EventsRunner
      TOLERANCE = 1e-9

      module_function

      def run(spec_root)
        path = File.join(spec_root, "events", "vectors.json")
        doc = ::JSON.parse(File.read(path))
        doc["vectors"].map { |v| run_one(v) }
      end

      def run_one(v)
        name = v["name"] || "?"
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

        sink = IAIso::Audit::MemorySink.new
        exec_id = v["execution_id"] || "?"
        engine =
          begin
            IAIso::Core::PressureEngine.new(
              config: cfg,
              options: IAIso::Core::EngineOptions.new(
                execution_id: exec_id, audit_sink: sink, clock: clk, timestamp_clock: clk,
              ),
            )
          rescue => e
            return VectorResult.fail("events", name, "engine init failed: #{e.message}")
          end

        reset_after_step = v["reset_after_step"]
        steps = v["steps"] || []
        steps.each_with_index do |step, i|
          if step["reset"]
            engine.reset
          else
            kw2 = {}
            kw2[:tokens] = step["tokens"].to_i if step.key?("tokens")
            kw2[:tool_calls] = step["tool_calls"].to_i if step.key?("tool_calls")
            kw2[:depth] = step["depth"].to_i if step.key?("depth")
            kw2[:tag] = step["tag"] if step.key?("tag")
            engine.step(IAIso::Core::StepInput.build(**kw2))
          end
          # 1-based: reset_after_step = N triggers after running step N
          if reset_after_step && (i + 1) == reset_after_step
            engine.reset
          end
        end

        got = sink.events
        expected = v["expected_events"] || []
        if got.size != expected.size
          return VectorResult.fail("events", name, "event count: got #{got.size}, want #{expected.size}")
        end
        expected.each_with_index do |exp, i|
          actual = got[i]
          if exp["schema_version"] && exp["schema_version"] != "" && exp["schema_version"] != actual.schema_version
            return VectorResult.fail("events", name, "event #{i} schema_version: got #{actual.schema_version}, want #{exp["schema_version"]}")
          end
          if exp["execution_id"] && exp["execution_id"] != "" && exp["execution_id"] != actual.execution_id
            return VectorResult.fail("events", name, "event #{i} execution_id: got #{actual.execution_id}, want #{exp["execution_id"]}")
          end
          if exp["kind"] && exp["kind"] != actual.kind
            return VectorResult.fail("events", name, "event #{i} kind: got #{actual.kind}, want #{exp["kind"]}")
          end
          if exp["data"].is_a?(Hash)
            unless data_matches?(actual.data, exp["data"])
              return VectorResult.fail("events", name, "event #{i} data mismatch: got #{actual.data}, want #{exp["data"]}")
            end
          end
        end
        VectorResult.pass("events", name)
      end

      def data_matches?(actual, want)
        # Actual data uses string keys; compare each key in want.
        want.each do |k, w|
          got = actual[k] || actual[k.to_sym]
          return false unless value_equal?(got, w)
        end
        true
      end

      def value_equal?(actual, want)
        return actual.nil? if want.nil?
        return false if actual.nil?
        return actual == want if [true, false].include?(want)
        if want.is_a?(Numeric)
          return false unless actual.is_a?(Numeric)
          return (actual.to_f - want.to_f).abs <= TOLERANCE
        end
        return actual == want if want.is_a?(String)
        if want.is_a?(Array)
          return false unless actual.is_a?(Array) && actual.size == want.size
          want.each_with_index do |w, i|
            return false unless value_equal?(actual[i], w)
          end
          return true
        end
        if want.is_a?(Hash)
          return false unless actual.is_a?(Hash)
          want.each do |k, w|
            a = actual[k] || actual[k.to_sym]
            return false unless value_equal?(a, w)
          end
          return true
        end
        false
      end
    end
  end
end
