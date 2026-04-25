# frozen_string_literal: true

require_relative "errors"
require_relative "../core/pressure_engine"
require_relative "../core/step_outcome"

module IAIso
  module Middleware
    module Mistral
      Usage = Data.define(:prompt_tokens, :completion_tokens, :total_tokens) do
        def self.empty = new(prompt_tokens: 0, completion_tokens: 0, total_tokens: 0)
      end
      Choice = Data.define(:tool_calls) do
        def self.empty = new(tool_calls: [])
      end
      Response = Data.define(:model, :usage, :choices)

      Options = Data.define(:raise_on_escalation) do
        def self.defaults = new(raise_on_escalation: false)
      end

      class BoundedClient
        def initialize(raw:, execution:, options: Options.defaults)
          @raw = raw
          @execution = execution
          @options = options
        end

        def chat_complete(params)
          pre = @execution.check
          raise LockedError if pre == IAIso::Core::StepOutcome::LOCKED
          if pre == IAIso::Core::StepOutcome::ESCALATED && @options.raise_on_escalation
            raise EscalationRaisedError
          end
          resp =
            begin
              @raw.chat_complete(params)
            rescue StandardError => e
              raise ProviderError, e.message
            end
          tokens = resp.usage.total_tokens.to_i
          tokens = resp.usage.prompt_tokens.to_i + resp.usage.completion_tokens.to_i if tokens.zero?
          tool_calls = resp.choices.sum { |c| c.tool_calls.size }
          model = resp.model.to_s.empty? ? "unknown" : resp.model
          @execution.record_step(IAIso::Core::StepInput.build(
            tokens: tokens, tool_calls: tool_calls,
            tag: "mistral.chat.complete:#{model}",
          ))
          resp
        end
      end
    end
  end
end
