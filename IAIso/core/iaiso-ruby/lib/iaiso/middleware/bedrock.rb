# frozen_string_literal: true

require_relative "errors"
require_relative "../core/pressure_engine"
require_relative "../core/step_outcome"

module IAIso
  module Middleware
    # AWS Bedrock middleware. Supports Converse (preferred) and the
    # lower-level InvokeModel API.
    module Bedrock
      ConverseUsage = Data.define(:input_tokens, :output_tokens, :total_tokens) do
        def self.empty = new(input_tokens: 0, output_tokens: 0, total_tokens: 0)
      end
      ConverseContentBlock = Data.define(:has_tool_use)
      ConverseResponse = Data.define(:usage, :content)
      InvokeResponse = Data.define(:model_id, :body) do
        def self.empty = new(model_id: "", body: "")
      end

      Options = Data.define(:raise_on_escalation) do
        def self.defaults = new(raise_on_escalation: false)
      end

      class BoundedClient
        def initialize(raw:, execution:, options: Options.defaults)
          @raw = raw
          @execution = execution
          @options = options
        end

        def converse(params)
          check_state!
          resp =
            begin
              @raw.converse(params)
            rescue StandardError => e
              raise ProviderError, e.message
            end
          tokens = resp.usage.total_tokens.to_i
          tokens = resp.usage.input_tokens.to_i + resp.usage.output_tokens.to_i if tokens.zero?
          tool_calls = resp.content.count { |b| b.has_tool_use }
          model_id = params[:modelId] || params["modelId"] || "unknown"
          @execution.record_step(IAIso::Core::StepInput.build(
            tokens: tokens, tool_calls: tool_calls,
            tag: "bedrock.converse:#{model_id}",
          ))
          resp
        end

        def invoke_model(params)
          check_state!
          resp =
            begin
              @raw.invoke_model(params)
            rescue StandardError => e
              raise ProviderError, e.message
            end
          model_id = !resp.model_id.to_s.empty? ? resp.model_id : (params[:modelId] || params["modelId"] || "unknown")
          @execution.record_step(IAIso::Core::StepInput.build(
            tag: "bedrock.invokeModel:#{model_id}",
          ))
          resp
        end

        private

        def check_state!
          pre = @execution.check
          raise LockedError if pre == IAIso::Core::StepOutcome::LOCKED
          if pre == IAIso::Core::StepOutcome::ESCALATED && @options.raise_on_escalation
            raise EscalationRaisedError
          end
        end
      end
    end
  end
end
