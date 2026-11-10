# frozen_string_literal: true

module IAIso
  module Policy
    # Aggregator interface (documentation; duck-typed).
    module Aggregator
      def name; raise NotImplementedError; end
      def aggregate(pressures); raise NotImplementedError; end
    end

    # Sum of per-execution pressures.
    class SumAggregator
      def name = "sum"
      def aggregate(pressures)
        pressures.values.sum.to_f
      end
    end

    # Arithmetic mean.
    class MeanAggregator
      def name = "mean"
      def aggregate(pressures)
        return 0.0 if pressures.empty?
        pressures.values.sum.to_f / pressures.size
      end
    end

    # Maximum.
    class MaxAggregator
      def name = "max"
      def aggregate(pressures)
        return 0.0 if pressures.empty?
        pressures.values.max.to_f
      end
    end

    # Weighted sum.
    class WeightedSumAggregator
      attr_reader :weights, :default_weight

      def initialize(weights:, default_weight: 1.0)
        @weights = weights || {}
        @default_weight = default_weight.to_f
      end

      def name = "weighted_sum"

      def aggregate(pressures)
        total = 0.0
        pressures.each do |k, v|
          w = @weights[k.to_s] || @default_weight
          total += w * v
        end
        total
      end
    end
  end
end
