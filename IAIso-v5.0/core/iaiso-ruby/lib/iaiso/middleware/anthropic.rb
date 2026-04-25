# frozen_string_literal: true

require_relative "errors"
require_relative "../core/pressure_engine"
require_relative "../core/step_outcome"

module IAIso
  module Middleware
    # Anthropic Messages API middleware.
    module Anthropic
      # Response struct — minimal subset of fields we account against.
      Response = Data.define(:model, :input_tokens, :output_tokens, :content)

      # A single content block. `type` is "text" or "tool_use".
      ContentBlock = Data.define(:type)

      Options = Data.define(:raise_on_escalation) do
        def self.defaults = new(raise_on_escalation: false)
      end

      # Wraps a duck-typed `raw` client (any object responding to
      # `messages_create(params) -> Response`) so every call is
      # accounted against a BoundedExecution.
      class BoundedClient
        def initialize(raw:, execution:, options: Options.defaults)
          @raw = raw
          @execution = execution
          @options = options
        end

        def messages_create(params)
          pre = @execution.check
          raise LockedError if pre == IAIso::Core::StepOutcome::LOCKED
          if pre == IAIso::Core::StepOutcome::ESCALATED && @options.raise_on_escalation
            raise EscalationRaisedError
          end
          resp =
            begin
              @raw.messages_create(params)
            rescue StandardError => e
              raise ProviderError, e.message
            end
          tokens = resp.input_tokens.to_i + resp.output_tokens.to_i
          tool_calls = resp.content.count { |b| b.type == "tool_use" }
          model = resp.model.to_s.empty? ? "unknown" : resp.model
          @execution.record_step(IAIso::Core::StepInput.build(
            tokens: tokens, tool_calls: tool_calls,
            tag: "anthropic.messages.create:#{model}",
          ))
          resp
        end
      end
    end
  end
end
