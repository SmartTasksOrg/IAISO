import Foundation

/// Discards events.
public final class NullSink: Sink {
    public static let shared = NullSink()
    private init() {}
    public func emit(_ event: Event) { /* discard */ }
}
