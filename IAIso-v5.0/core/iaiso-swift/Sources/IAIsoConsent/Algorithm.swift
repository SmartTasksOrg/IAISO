import Foundation

/// Supported JWT signature algorithms. The raw value is the wire form.
public enum Algorithm: String, Sendable, CaseIterable {
    case hs256 = "HS256"
    case rs256 = "RS256"
}
