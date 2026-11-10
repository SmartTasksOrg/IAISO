import Foundation

/// Scope-matching logic.
public enum Scopes {

    /// Returns true iff `requested` is granted by any scope in `granted`.
    /// Match rules per `spec/consent/README.md`:
    ///
    /// - Exact match: granted "tools.search" satisfies requested "tools.search".
    /// - Prefix-at-segment-boundary: granted "tools" satisfies requested "tools.search"
    ///   (boundary is the dot).
    /// - Substring without boundary does NOT match: "tools" does not satisfy "toolsbar".
    /// - More-specific does NOT satisfy less-specific: "tools.search.bulk" does
    ///   not satisfy "tools.search".
    ///
    /// - Throws: `ScopesError.emptyRequested` if `requested` is empty.
    public static func granted(_ granted: [String], _ requested: String) throws -> Bool {
        if requested.isEmpty {
            throw ScopesError.emptyRequested
        }
        for g in granted {
            if g == requested { return true }
            if requested.hasPrefix(g + ".") { return true }
        }
        return false
    }
}

public enum ScopesError: Error, CustomStringConvertible, Sendable {
    case emptyRequested
    public var description: String {
        switch self {
        case .emptyRequested: return "requested scope must be non-empty"
        }
    }
}
