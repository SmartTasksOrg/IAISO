import Foundation

/// A coordinator aggregation strategy.
public protocol Aggregator: Sendable {
    /// Wire-format aggregator name.
    var name: String { get }

    /// Compute the aggregate from per-execution pressures.
    func aggregate(_ pressures: [String: Double]) -> Double
}

/// Sum of per-execution pressures.
public struct SumAggregator: Aggregator {
    public init() {}
    public var name: String { "sum" }
    public func aggregate(_ pressures: [String: Double]) -> Double {
        return pressures.values.reduce(0, +)
    }
}

/// Arithmetic mean of per-execution pressures.
public struct MeanAggregator: Aggregator {
    public init() {}
    public var name: String { "mean" }
    public func aggregate(_ pressures: [String: Double]) -> Double {
        if pressures.isEmpty { return 0 }
        return pressures.values.reduce(0, +) / Double(pressures.count)
    }
}

/// Maximum of per-execution pressures.
public struct MaxAggregator: Aggregator {
    public init() {}
    public var name: String { "max" }
    public func aggregate(_ pressures: [String: Double]) -> Double {
        return pressures.values.max() ?? 0
    }
}

/// Weighted sum of per-execution pressures.
public struct WeightedSumAggregator: Aggregator {
    public let weights: [String: Double]
    public let defaultWeight: Double

    public init(weights: [String: Double], defaultWeight: Double = 1.0) {
        self.weights = weights
        self.defaultWeight = defaultWeight
    }

    public var name: String { "weighted_sum" }

    public func aggregate(_ pressures: [String: Double]) -> Double {
        var total = 0.0
        for (k, v) in pressures {
            let w = weights[k] ?? defaultWeight
            total += w * v
        }
        return total
    }
}
