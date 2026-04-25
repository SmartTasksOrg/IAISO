import Foundation

/// Raised when a `PressureConfig` is invalid.
public struct ConfigError: Error, CustomStringConvertible, Sendable {
    public let message: String
    public init(_ message: String) { self.message = message }
    public var description: String { message }
}
