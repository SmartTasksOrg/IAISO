import Foundation
import IAIsoAudit

public protocol Counter {
    func inc()
}

public protocol CounterVec {
    func labels(_ values: [String]) -> Counter
}

public protocol Gauge {
    func set(_ v: Double)
}

public protocol GaugeVec {
    func labels(_ values: [String]) -> Gauge
}

public protocol Histogram {
    func observe(_ v: Double)
}
