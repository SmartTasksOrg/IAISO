# frozen_string_literal: true

require "json"
require_relative "result"
require_relative "../policy"

module IAIso
  module Conformance
    module PolicyRunner
      TOLERANCE = 1e-9

      module_function

      def run(spec_root)
        path = File.join(spec_root, "policy", "vectors.json")
        doc = ::JSON.parse(File.read(path))
        out = []
        (doc["valid"] || []).each { |v| out << run_valid(v) }
        (doc["invalid"] || []).each { |v| out << run_invalid(v) }
        out
      end

      def run_valid(v)
        name = "valid/#{v["name"]}"
        p = IAIso::Policy::Loader.build(v["document"])
        if v["expected_pressure"].is_a?(Hash)
          err = check_pressure(p, v["expected_pressure"])
          return VectorResult.fail("policy", name, err) if err
        end
        if v["expected_consent"].is_a?(Hash)
          err = check_consent(p, v["expected_consent"])
          return VectorResult.fail("policy", name, err) if err
        end
        if v["expected_metadata"].is_a?(Hash)
          if v["expected_metadata"].size != p.metadata.size
            return VectorResult.fail("policy", name, "metadata size: got #{p.metadata.size}, want #{v["expected_metadata"].size}")
          end
        end
        VectorResult.pass("policy", name)
      rescue => e
        VectorResult.fail("policy", name, "build failed: #{e.message}")
      end

      def check_pressure(p, ep)
        checks = {
          "token_coefficient"      => p.pressure.token_coefficient,
          "tool_coefficient"       => p.pressure.tool_coefficient,
          "depth_coefficient"      => p.pressure.depth_coefficient,
          "dissipation_per_step"   => p.pressure.dissipation_per_step,
          "dissipation_per_second" => p.pressure.dissipation_per_second,
          "escalation_threshold"   => p.pressure.escalation_threshold,
          "release_threshold"      => p.pressure.release_threshold,
        }
        checks.each do |k, got|
          next unless ep.key?(k)
          want = ep[k].to_f
          if (got - want).abs > TOLERANCE
            return "#{k}: got #{got}, want #{want}"
          end
        end
        if ep.key?("post_release_lock")
          return "post_release_lock mismatch" if ep["post_release_lock"] != p.pressure.post_release_lock
        end
        nil
      end

      def check_consent(p, ec)
        if ec.key?("issuer")
          if ec["issuer"] != p.consent.issuer
            return "consent.issuer: got #{p.consent.issuer.inspect}, want #{ec["issuer"].inspect}"
          end
        end
        if ec.key?("default_ttl_seconds")
          want = ec["default_ttl_seconds"].to_f
          if (p.consent.default_ttl_seconds - want).abs > TOLERANCE
            return "default_ttl_seconds: got #{p.consent.default_ttl_seconds}, want #{want}"
          end
        end
        if ec.key?("required_scopes")
          if ec["required_scopes"].size != p.consent.required_scopes.size
            return "required_scopes length mismatch"
          end
        end
        if ec.key?("allowed_algorithms")
          if ec["allowed_algorithms"].size != p.consent.allowed_algorithms.size
            return "allowed_algorithms length mismatch"
          end
        end
        nil
      end

      def run_invalid(v)
        name = "invalid/#{v["name"]}"
        IAIso::Policy::Loader.build(v["document"])
        VectorResult.fail("policy", name, "expected error containing '#{v["expect_error_path"]}', got Ok")
      rescue IAIso::Policy::PolicyError => e
        return VectorResult.fail("policy", name, "expected error containing '#{v["expect_error_path"]}', got: #{e.message}") unless e.message.include?(v["expect_error_path"])
        VectorResult.pass("policy", name)
      end
    end
  end
end
