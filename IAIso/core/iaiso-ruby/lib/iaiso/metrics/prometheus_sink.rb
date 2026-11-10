# frozen_string_literal: true

module IAIso
  module Metrics
    # IAIso Prometheus metrics sink.
    #
    # Duck-typed — this module doesn't depend on any specific Prometheus
    # client gem. The official `prometheus-client` gem satisfies these
    # contracts with thin adapters.
    #
    # Required interfaces (duck typing):
    #   counter_vec.labels(label_value).increment
    #   counter.increment
    #   gauge_vec.labels(label_value).set(v)
    #   histogram.observe(v)
    class PrometheusSink
      # Suggested histogram buckets for `iaiso_step_delta`.
      SUGGESTED_HISTOGRAM_BUCKETS = [0.0, 0.01, 0.03, 0.05, 0.1, 0.2, 0.5, 1.0].freeze

      def initialize(events: nil, escalations: nil, releases: nil,
                     pressure: nil, step_delta: nil)
        @events = events
        @escalations = escalations
        @releases = releases
        @pressure = pressure
        @step_delta = step_delta
      end

      def emit(event)
        @events&.labels(event.kind)&.increment
        case event.kind
        when "engine.escalation"
          @escalations&.increment
        when "engine.release"
          @releases&.increment
        when "engine.step"
          p = event.data["pressure"] || event.data[:pressure]
          @pressure&.labels(event.execution_id)&.set(p.to_f) if p.is_a?(Numeric)
          d = event.data["delta"] || event.data[:delta]
          @step_delta&.observe(d.to_f) if d.is_a?(Numeric)
        end
      end
    end
  end
end
