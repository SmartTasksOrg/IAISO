import Foundation
import IAIsoAudit

/// A single step's worth of work.
public struct StepInput: Sendable, Equatable {
    public var tokens: Int64
    public var toolCalls: Int64
    public var depth: Int64
    public var tag: String?

    public init(tokens: Int64 = 0, toolCalls: Int64 = 0, depth: Int64 = 0, tag: String? = nil) {
        self.tokens = tokens
        self.toolCalls = toolCalls
        self.depth = depth
        self.tag = tag
    }

    public static let empty = StepInput()
}

/// Read-only snapshot of engine state.
public struct PressureSnapshot: Sendable, Equatable {
    public let pressure: Double
    public let step: Int64
    public let lifecycle: Lifecycle
    public let lastStepAt: Double

    public init(pressure: Double, step: Int64, lifecycle: Lifecycle, lastStepAt: Double) {
        self.pressure = pressure
        self.step = step
        self.lifecycle = lifecycle
        self.lastStepAt = lastStepAt
    }
}

/// Options for `PressureEngine` and `BoundedExecution`.
public struct EngineOptions: Sendable {
    public var executionId: String
    public var auditSink: Sink
    public var clock: Clock
    public var timestampClock: Clock

    public init(
        executionId: String,
        auditSink: Sink = NullSink.shared,
        clock: Clock = WallClock.shared,
        timestampClock: Clock? = nil
    ) {
        self.executionId = executionId
        self.auditSink = auditSink
        self.clock = clock
        self.timestampClock = timestampClock ?? clock
    }
}
