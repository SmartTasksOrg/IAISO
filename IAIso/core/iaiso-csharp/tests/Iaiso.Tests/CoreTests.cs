using Iaiso.Audit;
using Iaiso.Core;

namespace Iaiso.Tests;

public sealed class CoreTests
{
    public void TestPressureConfigDefaults()
    {
        var c = PressureConfig.Defaults();
        Assert.EqualDouble(0.85, c.EscalationThreshold);
        Assert.EqualDouble(0.95, c.ReleaseThreshold);
        Assert.True(c.PostReleaseLock);
    }

    public void TestPressureConfigValidation()
    {
        Assert.Throws<ConfigException>(() =>
            PressureConfig.CreateBuilder().WithReleaseThreshold(0.5)
                .WithEscalationThreshold(0.9).Build().Validate());
        Assert.Throws<ConfigException>(() =>
            PressureConfig.CreateBuilder().WithTokenCoefficient(-0.1).Build().Validate());
    }

    public void TestEngineEmitsInit()
    {
        var sink = new MemorySink();
        var engine = new PressureEngine(PressureConfig.Defaults(), new EngineOptions
        {
            ExecutionId = "test-1",
            AuditSink = sink,
            Clock = new ScriptedClock(0.0),
        });
        Assert.Equal(1, sink.Events().Count);
        Assert.Equal("engine.init", sink.Events()[0].Kind);
    }

    public void TestEngineStepIncrementsPressure()
    {
        // 5000 tokens at default coefficient (0.015 per 1000) = 0.075,
        // minus default dissipation (0.02) = 0.055 net.
        var engine = new PressureEngine(PressureConfig.Defaults(), new EngineOptions
        {
            Clock = new ScriptedClock(0.0, 1.0),
        });
        var outcome = engine.Step(new StepInput { Tokens = 5000 });
        Assert.Equal(StepOutcome.Ok, outcome);
        Assert.True(engine.Pressure > 0.0);
    }

    public void TestEngineEscalates()
    {
        var cfg = PressureConfig.CreateBuilder()
            .WithEscalationThreshold(0.4)
            .WithReleaseThreshold(0.99)
            .WithDepthCoefficient(0.5)
            .WithDissipationPerStep(0.0)
            .Build();
        var engine = new PressureEngine(cfg, new EngineOptions
        {
            Clock = new ScriptedClock(0.0, 1.0),
        });
        var outcome = engine.Step(new StepInput { Depth = 1 });
        Assert.Equal(StepOutcome.Escalated, outcome);
        Assert.Equal(Lifecycle.Escalated, engine.Lifecycle);
    }

    public void TestEngineLocksAfterRelease()
    {
        var cfg = PressureConfig.CreateBuilder()
            .WithEscalationThreshold(0.4)
            .WithReleaseThreshold(0.5)
            .WithDepthCoefficient(0.6)
            .WithDissipationPerStep(0.0)
            .WithPostReleaseLock(true)
            .Build();
        var engine = new PressureEngine(cfg, new EngineOptions
        {
            Clock = new ScriptedClock(0.0, 1.0, 2.0),
        });
        engine.Step(new StepInput { Depth = 1 });
        Assert.Equal(Lifecycle.Locked, engine.Lifecycle);
        // Subsequent step should be rejected
        var outcome = engine.Step(new StepInput { Tokens = 100 });
        Assert.Equal(StepOutcome.Locked, outcome);
    }

    public void TestEngineReset()
    {
        var sink = new MemorySink();
        var engine = new PressureEngine(PressureConfig.Defaults(), new EngineOptions
        {
            AuditSink = sink,
            Clock = new ScriptedClock(0.0, 1.0, 2.0),
        });
        engine.Step(new StepInput { Tokens = 1000 });
        engine.Reset();
        Assert.EqualDouble(0.0, engine.Pressure);
        Assert.Equal(Lifecycle.Init, engine.Lifecycle);
    }

    public void TestBoundedExecutionRunClosesEvenOnException()
    {
        var sink = new MemorySink();
        try
        {
            BoundedExecution.Run(
                new BoundedExecutionOptions { AuditSink = sink },
                exec => { throw new System.InvalidOperationException("boom"); });
        }
        catch (System.InvalidOperationException) { /* expected */ }
        bool foundClose = false;
        foreach (var e in sink.Events())
            if (e.Kind == "execution.closed")
            {
                foundClose = true;
                Assert.Equal((object?)"error", e.Data["exception"]);
            }
        Assert.True(foundClose);
    }

    public void TestBoundedExecutionRecordHelpers()
    {
        var sink = new MemorySink();
        using (var exec = BoundedExecution.Start(new BoundedExecutionOptions { AuditSink = sink }))
        {
            exec.RecordTokens(100, "t1");
            exec.RecordToolCall("search", 50);
        }
        int stepCount = 0;
        foreach (var e in sink.Events()) if (e.Kind == "engine.step") stepCount++;
        Assert.Equal(2, stepCount);
    }

    public void TestLifecycleWireFormat()
    {
        Assert.Equal("init", Lifecycle.Init.Wire());
        Assert.Equal("running", Lifecycle.Running.Wire());
        Assert.Equal("escalated", Lifecycle.Escalated.Wire());
        Assert.Equal("released", Lifecycle.Released.Wire());
        Assert.Equal("locked", Lifecycle.Locked.Wire());
    }
}
