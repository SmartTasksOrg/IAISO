import Foundation

/// A verified consent scope.
public struct Scope: Sendable, Equatable {
    public let token: String
    public let subject: String
    public let scopes: [String]
    public let executionId: String?
    public let jti: String
    public let issuedAt: Int64
    public let expiresAt: Int64
    public let metadata: [String: String]  // simple metadata; full JSON via re-parse

    public init(
        token: String,
        subject: String,
        scopes: [String],
        executionId: String?,
        jti: String,
        issuedAt: Int64,
        expiresAt: Int64,
        metadata: [String: String] = [:]
    ) {
        self.token = token
        self.subject = subject
        self.scopes = scopes
        self.executionId = executionId
        self.jti = jti
        self.issuedAt = issuedAt
        self.expiresAt = expiresAt
        self.metadata = metadata
    }

    /// True iff the verified scope set grants `requested`.
    public func grants(_ requested: String) throws -> Bool {
        return try Scopes.granted(scopes, requested)
    }

    /// Throws `ConsentError.insufficientScope` if any of `required`
    /// is not granted.
    public func require(_ required: [String]) throws {
        for r in required {
            if try !grants(r) {
                throw ConsentError.insufficientScope(required: r, granted: scopes)
            }
        }
    }
}
