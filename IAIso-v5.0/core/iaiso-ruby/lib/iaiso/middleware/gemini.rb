# frozen_string_literal: true

require_relative "errors"
require_relative "../core/pressure_engine"
require_relative "../core/step_outcome"

module IAIso
  module Middleware
    # Google Gemini / Vertex AI middleware.
    module Gemini
      UsageMetadata = Data.define(:prompt_token_count, :candidates_token_count, :total_token_count) do
        def self.empty = new(prompt_token_count: 0, candidates_token_count: 0, total_token_count: 0)
      end
      Part = Data.define(:has_function_call) do
        def self.empty = new(has_function_call: false)
      end
      Candidate = Data.define(:parts) do
        def self.empty = new(parts: [])
      end
      Response = Data.define(:usage_metadata, :candidates)

      Options = Data.define(:raise_on_escalation) do
        def self.defaults = new(raise_on_escalation: false)
      end

      class BoundedModel
        # `raw` is duck-typed: must respond to `generate_content(request) -> Response`
        # and `model_name -> String`.
        def initialize(raw:, execution:, options: Options.defaults)
          @raw = raw
          @execution = execution
          @options = options
        end

        def generate_content(request)
          pre = @execution.check
          raise LockedError if pre == IAIso::Core::StepOutcome::LOCKED
          if pre == IAIso::Core::StepOutcome::ESCALATED && @options.raise_on_escalation
            raise EscalationRaisedError
          end
          resp =
            begin
              @raw.generate_content(request)
            rescue StandardError => e
              raise ProviderError, e.message
            end
          tokens = resp.usage_metadata.total_token_count.to_i
          if tokens.zero?
            tokens = resp.usage_metadata.prompt_token_count.to_i + resp.usage_metadata.candidates_token_count.to_i
          end
          tool_calls = 0
          resp.candidates.each do |c|
            c.parts.each { |p| tool_calls += 1 if p.has_function_call }
          end
          model = @raw.respond_to?(:model_name) && !@raw.model_name.to_s.empty? ? @raw.model_name : "unknown"
          @execution.record_step(IAIso::Core::StepInput.build(
            tokens: tokens, tool_calls: tool_calls,
            tag: "gemini.generateContent:#{model}",
          ))
          resp
        end
      end
    end
  end
end
