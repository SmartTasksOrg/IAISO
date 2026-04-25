import Foundation

/// Read-only view of coordinator state.
public struct Snapshot: Sendable, Equatable {
    public let coordinatorId: String
    public let aggregatePressure: Double
    public let lifecycle: CoordinatorLifecycle
    public let activeExecutions: Int
    public let perExecution: [String: Double]

    public init(
        coordinatorId: String,
        aggregatePressure: Double,
        lifecycle: CoordinatorLifecycle,
        activeExecutions: Int,
        perExecution: [String: Double]
    ) {
        self.coordinatorId = coordinatorId
        self.aggregatePressure = aggregatePressure
        self.lifecycle = lifecycle
        self.activeExecutions = activeExecutions
        self.perExecution = perExecution
    }
}
