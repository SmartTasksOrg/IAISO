using System.Collections.Generic;
using System.Text.Json.Nodes;
using Iaiso.Audit;
using Iaiso.Core;
using Iaiso.Middleware;
using Iaiso.Middleware.Anthropic;

namespace Iaiso.Tests;

public sealed class MiddlewareTests
{
    private sealed class FakeAnthropicClient : IAnthropicClient
    {
        private readonly AnthropicResponse _resp;
        public FakeAnthropicClient(AnthropicResponse resp) { _resp = resp; }
        public AnthropicResponse MessagesCreate(JsonObject p) => _resp;
    }

    public void TestAnthropicAccountsTokensAndToolCalls()
    {
        var sink = new MemorySink();
        using var exec = BoundedExecution.Start(new BoundedExecutionOptions { AuditSink = sink });

        var raw = new FakeAnthropicClient(new AnthropicResponse(
            "claude-opus-4-7", 100, 250,
            new List<ContentBlock>
            {
                new("text"),
                new("tool_use"),
                new("tool_use"),
            }));
        var client = new BoundedAnthropicClient(raw, exec);
        client.MessagesCreate(new JsonObject());

        bool foundStep = false;
        foreach (var e in sink.Events())
        {
            if (e.Kind == "engine.step")
            {
                Assert.Equal(350L, (long)e.Data["tokens"]!);
                Assert.Equal(2L, (long)e.Data["tool_calls"]!);
                foundStep = true;
            }
        }
        Assert.True(foundStep, "expected engine.step event");
    }

    public void TestAnthropicRaisesOnEscalationWhenOptedIn()
    {
        var cfg = PressureConfig.CreateBuilder()
            .WithEscalationThreshold(0.4)
            .WithReleaseThreshold(0.95)
            .WithDepthCoefficient(0.5)
            .WithDissipationPerStep(0.0)
            .Build();
        using var exec = BoundedExecution.Start(new BoundedExecutionOptions { Config = cfg });
        // Force escalation
        exec.RecordStep(new StepInput { Depth = 1 });

        var raw = new FakeAnthropicClient(new AnthropicResponse("model", 0, 0, null));
        var client = new BoundedAnthropicClient(raw, exec, new AnthropicOptions { RaiseOnEscalation = true });
        Assert.Throws<MiddlewareException.EscalationRaised>(() =>
            client.MessagesCreate(new JsonObject()));
    }
}
