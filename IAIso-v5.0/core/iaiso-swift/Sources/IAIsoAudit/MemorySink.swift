import Foundation

/// Stores events in memory. Useful for tests.
public final class MemorySink: Sink, @unchecked Sendable {
    private let lock = NSLock()
    private var _events: [Event] = []

    public init() {}

    public func emit(_ event: Event) {
        lock.lock()
        defer { lock.unlock() }
        _events.append(event)
    }

    public var events: [Event] {
        lock.lock()
        defer { lock.unlock() }
        return _events
    }

    public func clear() {
        lock.lock()
        defer { lock.unlock() }
        _events.removeAll()
    }
}
