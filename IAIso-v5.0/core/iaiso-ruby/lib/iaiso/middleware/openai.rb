# frozen_string_literal: true

require_relative "errors"
require_relative "../core/pressure_engine"
require_relative "../core/step_outcome"

module IAIso
  module Middleware
    # OpenAI chat completions middleware. Also works for any
    # OpenAI-compatible endpoint (Azure OpenAI, vLLM, TGI, LiteLLM
    # proxy, Together, Groq, etc.).
    module OpenAI
      Usage = Data.define(:prompt_tokens, :completion_tokens, :total_tokens) do
        def self.empty = new(prompt_tokens: 0, completion_tokens: 0, total_tokens: 0)
      end

      ToolCall = Data.define(:id)
      Choice = Data.define(:tool_calls, :has_function_call) do
        def self.empty = new(tool_calls: [], has_function_call: false)
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

        def chat_completions_create(params)
          pre = @execution.check
          raise LockedError if pre == IAIso::Core::StepOutcome::LOCKED
          if pre == IAIso::Core::StepOutcome::ESCALATED && @options.raise_on_escalation
            raise EscalationRaisedError
          end
          resp =
            begin
              @raw.chat_completions_create(params)
            rescue StandardError => e
              raise ProviderError, e.message
            end
          tokens = resp.usage.total_tokens.to_i
          tokens = resp.usage.prompt_tokens.to_i + resp.usage.completion_tokens.to_i if tokens.zero?
          tool_calls = resp.choices.sum do |c|
            c.tool_calls.size + (c.has_function_call ? 1 : 0)
          end
          model = resp.model.to_s.empty? ? "unknown" : resp.model
          @execution.record_step(IAIso::Core::StepInput.build(
            tokens: tokens, tool_calls: tool_calls,
            tag: "openai.chat.completions.create:#{model}",
          ))
          resp
        end
      end
    end
  end
end
