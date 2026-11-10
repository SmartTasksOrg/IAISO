import Foundation

/// Issues consent tokens.
public final class Issuer: @unchecked Sendable {
    public let algorithm: Algorithm
    public let issuer: String
    public let defaultTTLSeconds: Int64
    private let hsKey: Data?
    private let rsPrivateKey: Data?
    private let clock: () -> Int64

    public init(
        algorithm: Algorithm = .hs256,
        issuer: String = "iaiso",
        hsKey: Data? = nil,
        rsPrivateKey: Data? = nil,
        defaultTTLSeconds: Int64 = 3600,
        clock: @escaping () -> Int64 = { Int64(Date().timeIntervalSince1970) }
    ) {
        self.algorithm = algorithm
        self.issuer = issuer
        self.hsKey = hsKey
        self.rsPrivateKey = rsPrivateKey
        self.defaultTTLSeconds = defaultTTLSeconds
        self.clock = clock
    }

    /// Issue a fresh token.
    public func issue(
        subject: String,
        scopes: [String],
        executionId: String? = nil,
        ttlSeconds: Int64? = nil,
        metadata: [String: Any]? = nil
    ) throws -> Scope {
        let now = clock()
        let ttl = ttlSeconds ?? defaultTTLSeconds
        let exp = now + ttl
        let jti = randomHex(16)

        // Spec field order: iss, sub, iat, exp, jti, scopes, [execution_id], [metadata]
        var pairs: [(String, Any)] = [
            ("iss", issuer),
            ("sub", subject),
            ("iat", Int64(now)),
            ("exp", Int64(exp)),
            ("jti", jti),
            ("scopes", scopes),
        ]
        if let executionId = executionId {
            pairs.append(("execution_id", executionId))
        }
        if let metadata = metadata, !metadata.isEmpty {
            pairs.append(("metadata", metadata))
        }

        // Build claims as ordered JSON.
        let claimsData = try JWT.canonicalJSONDataOrdered(pairs)
        let claimsB64 = Base64URL.encode(claimsData)

        // Header.
        let headerJSON = try JWT.canonicalJSONDataOrdered([
            ("alg", algorithm.rawValue),
            ("typ", "JWT"),
        ])
        let headerB64 = Base64URL.encode(headerJSON)
        let signingInput = headerB64 + "." + claimsB64
        guard let signingBytes = signingInput.data(using: .utf8) else {
            throw ConsentError.invalidToken(reason: "encode failed")
        }

        let signature: Data
        switch algorithm {
        case .hs256:
            guard let key = hsKey else {
                throw ConsentError.invalidToken(reason: "HS256 requires hsKey")
            }
            signature = JWT.hmacSha256(message: signingBytes, key: key)
        case .rs256:
            guard let priv = rsPrivateKey else {
                throw ConsentError.invalidToken(reason: "RS256 requires rsPrivateKey")
            }
            signature = try JWT.rsaSignSha256(message: signingBytes, privateKey: priv)
        }
        let token = signingInput + "." + Base64URL.encode(signature)

        // Build scope's metadata view (string values only — full dict re-parseable from token).
        var simpleMeta: [String: String] = [:]
        if let m = metadata {
            for (k, v) in m {
                if let s = v as? String { simpleMeta[k] = s }
            }
        }

        return Scope(
            token: token,
            subject: subject,
            scopes: scopes,
            executionId: executionId,
            jti: jti,
            issuedAt: now,
            expiresAt: exp,
            metadata: simpleMeta)
    }

    /// Generate a 64-byte base64url-no-pad HS256 secret.
    public static func generateHS256Secret() -> String {
        var d = Data(count: 64)
        for i in 0..<64 {
            d[i] = UInt8.random(in: 0...UInt8.max)
        }
        return Base64URL.encode(d)
    }

    private func randomHex(_ bytes: Int) -> String {
        var d = Data(count: bytes)
        for i in 0..<bytes {
            d[i] = UInt8.random(in: 0...UInt8.max)
        }
        return d.map { String(format: "%02x", $0) }.joined()
    }
}
