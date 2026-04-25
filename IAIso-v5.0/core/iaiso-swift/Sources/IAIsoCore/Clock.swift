import Foundation

/// Source of double-precision seconds since the epoch.
public protocol Clock: Sendable {
    func now() -> Double
}

/// Real time via `Date().timeIntervalSince1970`.
public final class WallClock: Clock {
    public static let shared = WallClock()
    private init() {}
    public func now() -> Double {
        return Date().timeIntervalSince1970
    }
}

/// Pre-recorded clock values; deterministic for tests.
public final class ScriptedClock: Clock, @unchecked Sendable {
    private let lock = NSLock()
    private var idx = 0
    private let sequence: [Double]

    public init(_ sequence: [Double]) {
        self.sequence = sequence
    }

    public func now() -> Double {
        lock.lock()
        defer { lock.unlock() }
        if sequence.isEmpty { return 0 }
        let i = idx
        idx += 1
        return i < sequence.count ? sequence[i] : sequence[sequence.count - 1]
    }

    public func reset() {
        lock.lock()
        defer { lock.unlock() }
        idx = 0
    }
}

/// Closure-backed clock.
public final class ClosureClock: Clock, @unchecked Sendable {
    private let fn: @Sendable () -> Double
    public init(_ fn: @escaping @Sendable () -> Double) { self.fn = fn }
    public func now() -> Double { fn() }
}
