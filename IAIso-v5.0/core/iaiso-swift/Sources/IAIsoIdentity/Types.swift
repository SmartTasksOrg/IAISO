import Foundation

/// Errors raised by the identity module.
public struct IdentityError: Error, CustomStringConvertible, Sendable {
    public let message: String
    public init(_ message: String) { self.message = message }
    public var description: String { message }
}

/// Configuration for an `OidcVerifier`.
public struct ProviderConfig: Sendable, Equatable {
    public var discoveryURL: String?
    public var jwksURL: String?
    public var issuer: String?
    public var audience: String?
    public var allowedAlgorithms: [String]
    public var leewaySeconds: Int64

    public init(
        discoveryURL: String? = nil,
        jwksURL: String? = nil,
        issuer: String? = nil,
        audience: String? = nil,
        allowedAlgorithms: [String] = ["RS256"],
        leewaySeconds: Int64 = 5
    ) {
        self.discoveryURL = discoveryURL
        self.jwksURL = jwksURL
        self.issuer = issuer
        self.audience = audience
        self.allowedAlgorithms = allowedAlgorithms
        self.leewaySeconds = leewaySeconds
    }

    public static let defaults = ProviderConfig()

    public static func okta(domain: String, audience: String) -> ProviderConfig {
        return ProviderConfig(
            discoveryURL: "https://\(domain)/.well-known/openid-configuration",
            issuer: "https://\(domain)",
            audience: audience)
    }

    public static func auth0(domain: String, audience: String) -> ProviderConfig {
        return ProviderConfig(
            discoveryURL: "https://\(domain)/.well-known/openid-configuration",
            issuer: "https://\(domain)/",
            audience: audience)
    }

    public static func azureAd(tenant: String, audience: String, v2: Bool = true) -> ProviderConfig {
        let base = v2
            ? "https://login.microsoftonline.com/\(tenant)/v2.0"
            : "https://login.microsoftonline.com/\(tenant)"
        return ProviderConfig(
            discoveryURL: "\(base)/.well-known/openid-configuration",
            issuer: base,
            audience: audience)
    }
}

/// Configures how OIDC claims become IAIso scopes.
public struct ScopeMapping: Sendable, Equatable {
    public var directClaims: [String]
    public var groupToScopes: [String: [String]]
    public var alwaysGrant: [String]

    public init(
        directClaims: [String] = [],
        groupToScopes: [String: [String]] = [:],
        alwaysGrant: [String] = []
    ) {
        self.directClaims = directClaims
        self.groupToScopes = groupToScopes
        self.alwaysGrant = alwaysGrant
    }

    public static let defaults = ScopeMapping()
}

/// A single key from a JWKS document.
public struct Jwk: Sendable, Equatable {
    public let kty: String
    public let kid: String?
    public let alg: String?
    public let use: String?
    public let n: String?
    public let e: String?

    public init(
        kty: String,
        kid: String? = nil,
        alg: String? = nil,
        use: String? = nil,
        n: String? = nil,
        e: String? = nil
    ) {
        self.kty = kty
        self.kid = kid
        self.alg = alg
        self.use = use
        self.n = n
        self.e = e
    }
}

public struct Jwks: Sendable, Equatable {
    public let keys: [Jwk]
    public init(keys: [Jwk]) { self.keys = keys }
}
