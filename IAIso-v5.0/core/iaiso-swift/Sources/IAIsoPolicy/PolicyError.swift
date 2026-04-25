import Foundation

/// Wraps a policy validation failure.
public struct PolicyError: Error, CustomStringConvertible, Sendable {
    public let message: String
    public init(_ message: String) { self.message = message }
    public var description: String { message }
}
