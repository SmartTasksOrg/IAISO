import Foundation

/// Validated configuration for a `PressureEngine`.
public struct PressureConfig: Sendable, Equatable {
    public var tokenCoefficient: Double
    public var toolCoefficient: Double
    public var depthCoefficient: Double
    public var dissipationPerStep: Double
    public var dissipationPerSecond: Double
    public var escalationThreshold: Double
    public var releaseThreshold: Double
    public var postReleaseLock: Bool

    public init(
        tokenCoefficient: Double = 0.015,
        toolCoefficient: Double = 0.08,
        depthCoefficient: Double = 0.05,
        dissipationPerStep: Double = 0.02,
        dissipationPerSecond: Double = 0.0,
        escalationThreshold: Double = 0.85,
        releaseThreshold: Double = 0.95,
        postReleaseLock: Bool = true
    ) {
        self.tokenCoefficient = tokenCoefficient
        self.toolCoefficient = toolCoefficient
        self.depthCoefficient = depthCoefficient
        self.dissipationPerStep = dissipationPerStep
        self.dissipationPerSecond = dissipationPerSecond
        self.escalationThreshold = escalationThreshold
        self.releaseThreshold = releaseThreshold
        self.postReleaseLock = postReleaseLock
    }

    public static let defaults = PressureConfig()

    /// Throws `ConfigError` if any field is out of range.
    public func validate() throws {
        let nonNeg: [(String, Double)] = [
            ("token_coefficient", tokenCoefficient),
            ("tool_coefficient", toolCoefficient),
            ("depth_coefficient", depthCoefficient),
            ("dissipation_per_step", dissipationPerStep),
            ("dissipation_per_second", dissipationPerSecond),
        ]
        for (name, val) in nonNeg {
            if val < 0 {
                throw ConfigError("\(name) must be non-negative (got \(val))")
            }
        }
        if escalationThreshold < 0 || escalationThreshold > 1 {
            throw ConfigError(
                "escalation_threshold must be in [0, 1] (got \(escalationThreshold))")
        }
        if releaseThreshold < 0 || releaseThreshold > 1 {
            throw ConfigError(
                "release_threshold must be in [0, 1] (got \(releaseThreshold))")
        }
        if releaseThreshold <= escalationThreshold {
            throw ConfigError(
                "release_threshold must exceed escalation_threshold (\(releaseThreshold) <= \(escalationThreshold))")
        }
    }
}
