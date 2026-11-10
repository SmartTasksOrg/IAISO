# frozen_string_literal: true

require_relative "test_helper"
require "iaiso/audit"
require "iaiso/core"
require "iaiso/middleware"

class MiddlewareTest < Minitest::Test
  class FakeAnthropic
    def messages_create(_params)
      IAIso::Middleware::Anthropic::Response.new(
        model: "claude-opus-4-7",
        input_tokens: 100,
        output_tokens: 250,
        content: [
          IAIso::Middleware::Anthropic::ContentBlock.new(type: "text"),
          IAIso::Middleware::Anthropic::ContentBlock.new(type: "tool_use"),
          IAIso::Middleware::Anthropic::ContentBlock.new(type: "tool_use"),
        ],
      )
    end
  end

  def test_anthropic_accounts_tokens_and_tool_calls
    sink = IAIso::Audit::MemorySink.new
    exec = IAIso::Core::BoundedExecution.start(audit_sink: sink)
    client = IAIso::Middleware::Anthropic::BoundedClient.new(
      raw: FakeAnthropic.new, execution: exec,
    )
    client.messages_create({})
    step = sink.events.find { |e| e.kind == "engine.step" }
    refute_nil step
    assert_equal 350, step.data["tokens"]
    assert_equal 2, step.data["tool_calls"]
    exec.close
  end

  def test_raises_on_escalation_when_opted_in
    cfg = IAIso::Core::PressureConfig.new(
      escalation_threshold: 0.4, release_threshold: 0.95,
      depth_coefficient: 0.5, dissipation_per_step: 0.0,
    )
    exec = IAIso::Core::BoundedExecution.start(config: cfg)
    exec.record_step(IAIso::Core::StepInput.build(depth: 1))  # force escalation
    client = IAIso::Middleware::Anthropic::BoundedClient.new(
      raw: FakeAnthropic.new, execution: exec,
      options: IAIso::Middleware::Anthropic::Options.new(raise_on_escalation: true),
    )
    assert_raises(IAIso::Middleware::EscalationRaisedError) do
      client.messages_create({})
    end
  end
end
