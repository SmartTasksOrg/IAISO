# frozen_string_literal: true

require_relative "errors"
require_relative "../core/pressure_engine"
require_relative "../core/step_outcome"

module IAIso
  module Middleware
    module Cohere
      BilledUnits = Data.define(:input_tokens, :output_tokens) do
        def self.empty = new(input_tokens: 0, output_tokens: 0)
      end
      Meta = Data.define(:tokens, :billed_units) do
        def self.empty = new(tokens: nil, billed_units: nil)
      end
      ToolCall = Data.define(:name)
      Response = Data.define(:model, :meta, :tool_calls)

      Options = Data.define(:raise_on_escalation) do
        def self.defaults = new(raise_on_escalation: false)
      end

      class BoundedClient
        def initialize(raw:, execution:, options: Options.defaults)
          @raw = raw
          @execution = execution
          @options = options
        end

        def chat(params)
          pre = @execution.check
          raise LockedError if pre == IAIso::Core::StepOutcome::LOCKED
          if pre == IAIso::Core::StepOutcome::ESCALATED && @options.raise_on_escalation
            raise EscalationRaisedError
          end
          resp =
            begin
              @raw.chat(params)
            rescue StandardError => e
              raise ProviderError, e.message
            end
          billed = resp.meta.tokens || resp.meta.billed_units
          tokens = billed.nil? ? 0 : (billed.input_tokens.to_i + billed.output_tokens.to_i)
          tool_calls = resp.tool_calls.size
          model = resp.model.to_s.empty? ? "unknown" : resp.model
          @execution.record_step(IAIso::Core::StepInput.build(
            tokens: tokens, tool_calls: tool_calls,
            tag: "cohere.chat:#{model}",
          ))
          resp
        end
      end
    end
  end
end
