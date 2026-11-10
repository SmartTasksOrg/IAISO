import Foundation

/// Errors raised by the middleware layer.
public enum MiddlewareError: Error, CustomStringConvertible, Sendable {
    case escalationRaised
    case locked
    case provider(String, underlying: Error?)

    public var description: String {
        switch self {
        case .escalationRaised: return "execution escalated; raise-on-escalation enabled"
        case .locked: return "execution locked"
        case .provider(let msg, _): return "provider error: \(msg)"
        }
    }
}
