using System.Collections.Generic;

namespace Iaiso.Coordination;

/// <summary>Read-only view of coordinator state.</summary>
public sealed class Snapshot
{
    public string CoordinatorId { get; }
    public double AggregatePressure { get; }
    public CoordinatorLifecycle Lifecycle { get; }
    public int ActiveExecutions { get; }
    public IReadOnlyDictionary<string, double> PerExecution { get; }

    public Snapshot(string coordinatorId, double aggregatePressure,
                    CoordinatorLifecycle lifecycle, int activeExecutions,
                    IReadOnlyDictionary<string, double> perExecution)
    {
        CoordinatorId = coordinatorId;
        AggregatePressure = aggregatePressure;
        Lifecycle = lifecycle;
        ActiveExecutions = activeExecutions;
        PerExecution = new SortedDictionary<string, double>(
            new Dictionary<string, double>(perExecution));
    }
}
