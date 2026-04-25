import Foundation

/// Errors raised by the consent module.
public enum ConsentError: Error, CustomStringConvertible, Sendable {
    case invalidToken(reason: String)
    case expiredToken
    case revokedToken(jti: String)
    case insufficientScope(required: String, granted: [String])

    public var description: String {
        switch self {
        case .invalidToken(let reason):
            return "invalid token: \(reason)"
        case .expiredToken:
            return "token expired"
        case .revokedToken(let jti):
            return "token revoked: \(jti)"
        case .insufficientScope(let required, let granted):
            return "scope '\(required)' not granted; have [\(granted.joined(separator: ", "))]"
        }
    }
}
