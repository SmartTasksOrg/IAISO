import Foundation

/// Lifecycle state of a fleet-aggregated coordinator.
public enum CoordinatorLifecycle: String, Sendable, CaseIterable {
    case nominal = "nominal"
    case escalated = "escalated"
    case released = "released"
}

/// Wraps a coordinator failure.
public struct CoordinatorError: Error, CustomStringConvertible, Sendable {
    public let message: String
    public init(_ message: String) { self.message = message }
    public var description: String { message }
}
