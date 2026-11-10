using System.Text.Json.Nodes;
using Iaiso.Policy;

namespace Iaiso.Tests;

public sealed class PolicyTests
{
    public void TestBuildMinimalPolicy()
    {
        var p = PolicyLoader.Build(JsonNode.Parse("{\"version\":\"1\"}"));
        Assert.Equal("1", p.Version);
        Assert.Equal("sum", p.Aggregator.Name);
    }

    public void TestBuildOverridesDefaults()
    {
        var doc = "{\"version\":\"1\",\"pressure\":{\"escalation_threshold\":0.7,\"release_threshold\":0.85},\"coordinator\":{\"aggregator\":\"max\"}}";
        var p = PolicyLoader.Build(JsonNode.Parse(doc));
        Assert.EqualDouble(0.7, p.Pressure.EscalationThreshold);
        Assert.Equal("max", p.Aggregator.Name);
    }

    public void TestRejectsMissingVersion()
    {
        Assert.Throws<PolicyException>(() => PolicyLoader.Build(JsonNode.Parse("{}")));
    }

    public void TestRejectsBadVersion()
    {
        Assert.Throws<PolicyException>(() =>
            PolicyLoader.Build(JsonNode.Parse("{\"version\":\"2\"}")));
    }

    public void TestRejectsReleaseBelowEscalation()
    {
        Assert.Throws<PolicyException>(() =>
            PolicyLoader.Build(JsonNode.Parse(
                "{\"version\":\"1\",\"pressure\":{\"escalation_threshold\":0.9,\"release_threshold\":0.5}}")));
    }

    public void TestSumAggregator()
    {
        var m = new System.Collections.Generic.Dictionary<string, double>
        {
            ["a"] = 0.3, ["b"] = 0.5,
        };
        Assert.EqualDouble(0.8, new SumAggregator().Aggregate(m));
    }

    public void TestMaxAggregator()
    {
        var m = new System.Collections.Generic.Dictionary<string, double>
        {
            ["a"] = 0.3, ["b"] = 0.5,
        };
        Assert.EqualDouble(0.5, new MaxAggregator().Aggregate(m));
    }

    public void TestWeightedSumAggregator()
    {
        var w = new System.Collections.Generic.Dictionary<string, double>
        {
            ["important"] = 2.0,
        };
        var a = new WeightedSumAggregator(w, 1.0);
        var p = new System.Collections.Generic.Dictionary<string, double>
        {
            ["important"] = 0.5, ["normal"] = 0.3,
        };
        Assert.EqualDouble(1.3, a.Aggregate(p));
    }
}
