import Foundation
import IAIsoAudit

public protocol Span: AnyObject {
    func addEvent(_ name: String, attributes: [String: AnyJSON])
    func setAttribute(_ key: String, value: AnyJSON)
    func end()
}

public protocol Tracer {
    func startSpan(_ name: String, attributes: [String: AnyJSON]) -> Span
}

/// IAIso OpenTelemetry tracing sink.
///
/// Structurally typed against the OTel trace API. The community
/// swift-otel packages can satisfy these protocols with thin adapters.
public final class OtelSpanSink: Sink, @unchecked Sendable {
    private let tracer: Tracer
    private let spanName: String
    private let lock = NSLock()
    private var spans: [String: Span] = [:]

    public init(tracer: Tracer, spanName: String = "iaiso.execution") {
        self.tracer = tracer
        self.spanName = spanName
    }

    public func closeAll() {
        lock.lock()
        let all = Array(spans.values)
        spans.removeAll()
        lock.unlock()
        for s in all { s.end() }
    }

    public func emit(_ event: Event) {
        var span: Span?
        if event.kind == "engine.init" {
            let s = tracer.startSpan(
                "\(spanName):\(event.executionId)",
                attributes: ["iaiso.execution_id": .string(event.executionId)])
            lock.lock()
            spans[event.executionId] = s
            lock.unlock()
            span = s
        } else {
            lock.lock()
            span = spans[event.executionId]
            lock.unlock()
        }
        guard let span = span else { return }

        var attrs = event.data
        attrs["iaiso.schema_version"] = .string(event.schemaVersion)
        span.addEvent(event.kind, attributes: attrs)

        switch event.kind {
        case "engine.step":
            if let p = event.data["pressure"] {
                span.setAttribute("iaiso.pressure", value: p)
            }
        case "engine.escalation":
            span.setAttribute("iaiso.escalated", value: .bool(true))
        case "engine.release":
            span.setAttribute("iaiso.released", value: .bool(true))
        case "execution.closed":
            span.end()
            lock.lock()
            spans.removeValue(forKey: event.executionId)
            lock.unlock()
        default: break
        }
    }
}
