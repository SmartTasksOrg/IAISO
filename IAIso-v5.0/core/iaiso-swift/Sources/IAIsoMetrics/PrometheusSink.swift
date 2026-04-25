import Foundation
import IAIsoAudit

/// IAIso Prometheus metrics sink.
///
/// Structurally typed — this module doesn't depend on any specific
/// Prometheus client library. The community swift-prometheus packages
/// satisfy these protocols with thin adapters.
public final class PrometheusSink: Sink {
    /// Suggested histogram buckets for `iaiso_step_delta`.
    public static let suggestedHistogramBuckets: [Double] =
        [0.0, 0.01, 0.03, 0.05, 0.1, 0.2, 0.5, 1.0]

    private let events: CounterVec?
    private let escalations: Counter?
    private let releases: Counter?
    private let pressure: GaugeVec?
    private let stepDelta: Histogram?

    public init(
        events: CounterVec? = nil,
        escalations: Counter? = nil,
        releases: Counter? = nil,
        pressure: GaugeVec? = nil,
        stepDelta: Histogram? = nil
    ) {
        self.events = events
        self.escalations = escalations
        self.releases = releases
        self.pressure = pressure
        self.stepDelta = stepDelta
    }

    public func emit(_ event: Event) {
        events?.labels([event.kind]).inc()
        switch event.kind {
        case "engine.escalation":
            escalations?.inc()
        case "engine.release":
            releases?.inc()
        case "engine.step":
            if let p = event.data["pressure"]?.doubleValue {
                pressure?.labels([event.executionId]).set(p)
            }
            if let d = event.data["delta"]?.doubleValue {
                stepDelta?.observe(d)
            }
        default:
            break
        }
    }
}
