// swift-tools-version: 5.9
// IAIso — bounded-agent-execution framework, Swift reference SDK.
// Targets iOS 13+, macOS 10.15+, tvOS 13+, watchOS 6+, and Linux.

import PackageDescription

let package = Package(
    name: "iaiso-swift",
    platforms: [
        .iOS(.v13),
        .macOS(.v10_15),
        .tvOS(.v13),
        .watchOS(.v6),
    ],
    products: [
        // Each capability is its own library product so consumers add only what they need.
        .library(name: "IAIsoAudit",         targets: ["IAIsoAudit"]),
        .library(name: "IAIsoCore",          targets: ["IAIsoCore"]),
        .library(name: "IAIsoConsent",       targets: ["IAIsoConsent"]),
        .library(name: "IAIsoPolicy",        targets: ["IAIsoPolicy"]),
        .library(name: "IAIsoCoordination",  targets: ["IAIsoCoordination"]),
        .library(name: "IAIsoMiddleware",    targets: ["IAIsoMiddleware"]),
        .library(name: "IAIsoIdentity",      targets: ["IAIsoIdentity"]),
        .library(name: "IAIsoMetrics",       targets: ["IAIsoMetrics"]),
        .library(name: "IAIsoObservability", targets: ["IAIsoObservability"]),
        .library(name: "IAIsoConformance",   targets: ["IAIsoConformance"]),

        // Convenience aggregate that re-exports the most common modules.
        .library(name: "IAIso", targets: [
            "IAIsoAudit", "IAIsoCore", "IAIsoConsent", "IAIsoPolicy", "IAIsoCoordination",
        ]),

        // Admin CLI executable (macOS / Linux only — iOS apps don't ship CLIs).
        .executable(name: "iaiso", targets: ["IAIsoCLI"]),
    ],
    targets: [
        .target(name: "IAIsoAudit"),
        .target(name: "IAIsoCore", dependencies: ["IAIsoAudit"]),
        .target(name: "IAIsoConsent"),
        .target(name: "IAIsoPolicy", dependencies: ["IAIsoCore"]),
        .target(name: "IAIsoCoordination", dependencies: ["IAIsoAudit", "IAIsoCore", "IAIsoPolicy"]),
        .target(name: "IAIsoMiddleware", dependencies: ["IAIsoCore"]),
        .target(name: "IAIsoIdentity", dependencies: ["IAIsoConsent"]),
        .target(name: "IAIsoMetrics", dependencies: ["IAIsoAudit"]),
        .target(name: "IAIsoObservability", dependencies: ["IAIsoAudit"]),
        .target(
            name: "IAIsoConformance",
            dependencies: ["IAIsoAudit", "IAIsoCore", "IAIsoConsent", "IAIsoPolicy"]
        ),
        .executableTarget(
            name: "IAIsoCLI",
            dependencies: [
                "IAIsoAudit", "IAIsoCore", "IAIsoConsent",
                "IAIsoPolicy", "IAIsoCoordination", "IAIsoConformance",
            ]
        ),

        // Tests.
        .testTarget(name: "IAIsoAuditTests",        dependencies: ["IAIsoAudit"]),
        .testTarget(name: "IAIsoCoreTests",         dependencies: ["IAIsoCore", "IAIsoAudit"]),
        .testTarget(name: "IAIsoConsentTests",      dependencies: ["IAIsoConsent"]),
        .testTarget(name: "IAIsoPolicyTests",       dependencies: ["IAIsoPolicy"]),
        .testTarget(
            name: "IAIsoCoordinationTests",
            dependencies: ["IAIsoCoordination", "IAIsoAudit", "IAIsoPolicy"]
        ),
        .testTarget(name: "IAIsoIdentityTests",     dependencies: ["IAIsoIdentity", "IAIsoConsent"]),
        .testTarget(
            name: "IAIsoMiddlewareTests",
            dependencies: ["IAIsoMiddleware", "IAIsoCore", "IAIsoAudit"]
        ),
        .testTarget(
            name: "IAIsoConformanceTests",
            dependencies: ["IAIsoConformance"]
        ),
    ]
)
