# frozen_string_literal: true

require "monitor"

module IAIso
  module Observability
    # IAIso OpenTelemetry tracing sink.
    #
    # Duck-typed against the OTel trace API. The official
    # `opentelemetry-api` gem's tracer / span objects satisfy these
    # contracts with thin adapters.
    #
    # Required interfaces (duck typing):
    #   tracer.start_span(name, attributes:) -> span
    #   span.add_event(name, attributes: ...)
    #   span.set_attribute(key, value)
    #   span.finish
    class OtelSpanSink
      include MonitorMixin

      def initialize(tracer:, span_name: "iaiso.execution")
        super()
        @tracer = tracer
        @span_name = span_name
        @spans = {}
      end

      def emit(event)
        synchronize do
          if event.kind == "engine.init"
            @spans[event.execution_id] = @tracer.start_span(
              "#{@span_name}:#{event.execution_id}",
              attributes: { "iaiso.execution_id" => event.execution_id },
            )
          end
          span = @spans[event.execution_id]
          return if span.nil?

          attrs = event.data.merge("iaiso.schema_version" => event.schema_version)
          span.add_event(event.kind, attributes: attrs)
          case event.kind
          when "engine.step"
            span.set_attribute("iaiso.pressure", event.data["pressure"]) if event.data["pressure"]
          when "engine.escalation"
            span.set_attribute("iaiso.escalated", true)
          when "engine.release"
            span.set_attribute("iaiso.released", true)
          when "execution.closed"
            span.finish
            @spans.delete(event.execution_id)
          end
        end
      end

      def close_all
        synchronize do
          @spans.each_value { |s| s.finish rescue nil }
          @spans.clear
        end
      end
    end
  end
end
