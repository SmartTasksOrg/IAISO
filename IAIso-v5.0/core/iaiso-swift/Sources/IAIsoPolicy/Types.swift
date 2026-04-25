import Foundation
import IAIsoCore

/// Coordinator-section configuration from a parsed policy.
public struct CoordinatorConfig: Sendable, Equatable {
    public var escalationThreshold: Double
    public var releaseThreshold: Double
    public var notifyCooldownSeconds: Double

    public init(
        escalationThreshold: Double = 5.0,
        releaseThreshold: Double = 8.0,
        notifyCooldownSeconds: Double = 1.0
    ) {
        self.escalationThreshold = escalationThreshold
        self.releaseThreshold = releaseThreshold
        self.notifyCooldownSeconds = notifyCooldownSeconds
    }

    public static let defaults = CoordinatorConfig()
}

/// Consent-section configuration from a parsed policy.
public struct ConsentPolicy: Sendable, Equatable {
    public var issuer: String?
    public var defaultTTLSeconds: Double
    public var requiredScopes: [String]
    public var allowedAlgorithms: [String]

    public init(
        issuer: String? = nil,
        defaultTTLSeconds: Double = 3600,
        requiredScopes: [String] = [],
        allowedAlgorithms: [String] = ["HS256", "RS256"]
    ) {
        self.issuer = issuer
        self.defaultTTLSeconds = defaultTTLSeconds
        self.requiredScopes = requiredScopes
        self.allowedAlgorithms = allowedAlgorithms
    }

    public static let defaults = ConsentPolicy()
}

/// Assembled, validated policy document.
public struct Policy {
    public let version: String
    public let pressure: PressureConfig
    public let coordinator: CoordinatorConfig
    public let consent: ConsentPolicy
    public let aggregator: Aggregator
    public let metadata: [String: Any]

    public init(
        version: String,
        pressure: PressureConfig,
        coordinator: CoordinatorConfig,
        consent: ConsentPolicy,
        aggregator: Aggregator,
        metadata: [String: Any] = [:]
    ) {
        self.version = version
        self.pressure = pressure
        self.coordinator = coordinator
        self.consent = consent
        self.aggregator = aggregator
        self.metadata = metadata
    }
}
