import Foundation

/// Writes one canonical JSON object per event to standard output.
public final class StdoutSink: Sink {
    public static let shared = StdoutSink()
    private init() {}
    public func emit(_ event: Event) {
        print(event.toJSON())
    }
}
