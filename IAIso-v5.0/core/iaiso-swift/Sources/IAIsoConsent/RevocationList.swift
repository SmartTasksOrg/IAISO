import Foundation

/// Thread-safe set of revoked JTIs.
public final class RevocationList: @unchecked Sendable {
    private let lock = NSLock()
    private var set: Set<String> = []

    public init() {}

    public func revoke(_ jti: String) {
        lock.lock(); defer { lock.unlock() }
        set.insert(jti)
    }

    public func isRevoked(_ jti: String) -> Bool {
        lock.lock(); defer { lock.unlock() }
        return set.contains(jti)
    }

    public func clear() {
        lock.lock(); defer { lock.unlock() }
        set.removeAll()
    }
}
