# frozen_string_literal: true

module IAIso
  module Core
    class ConfigError < StandardError; end

    # Validated configuration for a PressureEngine.
    class PressureConfig
      attr_reader :token_coefficient, :tool_coefficient, :depth_coefficient,
                  :dissipation_per_step, :dissipation_per_second,
                  :escalation_threshold, :release_threshold, :post_release_lock

      def initialize(
        token_coefficient: 0.015,
        tool_coefficient: 0.08,
        depth_coefficient: 0.05,
        dissipation_per_step: 0.02,
        dissipation_per_second: 0.0,
        escalation_threshold: 0.85,
        release_threshold: 0.95,
        post_release_lock: true
      )
        @token_coefficient      = token_coefficient.to_f
        @tool_coefficient       = tool_coefficient.to_f
        @depth_coefficient      = depth_coefficient.to_f
        @dissipation_per_step   = dissipation_per_step.to_f
        @dissipation_per_second = dissipation_per_second.to_f
        @escalation_threshold   = escalation_threshold.to_f
        @release_threshold      = release_threshold.to_f
        @post_release_lock      = post_release_lock ? true : false
        freeze
      end

      def self.defaults = new

      # Raises ConfigError when invalid.
      def validate!
        non_neg = {
          "token_coefficient" => @token_coefficient,
          "tool_coefficient" => @tool_coefficient,
          "depth_coefficient" => @depth_coefficient,
          "dissipation_per_step" => @dissipation_per_step,
          "dissipation_per_second" => @dissipation_per_second,
        }
        non_neg.each do |k, v|
          raise ConfigError, "#{k} must be non-negative (got #{v})" if v < 0
        end
        unless (0..1).cover?(@escalation_threshold)
          raise ConfigError, "escalation_threshold must be in [0, 1] (got #{@escalation_threshold})"
        end
        unless (0..1).cover?(@release_threshold)
          raise ConfigError, "release_threshold must be in [0, 1] (got #{@release_threshold})"
        end
        if @release_threshold <= @escalation_threshold
          raise ConfigError,
                "release_threshold must exceed escalation_threshold (#{@release_threshold} <= #{@escalation_threshold})"
        end
        self
      end
    end
  end
end
