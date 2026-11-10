import Foundation

/// A consumer of audit events.
public protocol Sink: Sendable {
    func emit(_ event: Event)
}
