import Foundation

/// Forwards events to multiple sinks. Errors in one sink do not poison others.
public final class FanoutSink: Sink {
    private let sinks: [Sink]

    public init(_ sinks: [Sink]) {
        self.sinks = sinks
    }

    public convenience init(_ sinks: Sink...) {
        self.init(sinks)
    }

    public func emit(_ event: Event) {
        for s in sinks {
            s.emit(event)
        }
    }
}
