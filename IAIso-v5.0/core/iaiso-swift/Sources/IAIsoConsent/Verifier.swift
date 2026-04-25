import Foundation

/// Verifies signed consent tokens.
public final class Verifier: @unchecked Sendable {
    public let algorithm: Algorithm
    public let issuer: String
    public let leewaySeconds: Int64
    private let hsKey: Data?
    private let rsPublicKey: Data?
    private let revocationList: RevocationList?
    private let clock: () -> Int64

    public init(
        algorithm: Algorithm = .hs256,
        issuer: String = "iaiso",
        hsKey: Data? = nil,
        rsPublicKey: Data? = nil,
        revocationList: RevocationList? = nil,
        leewaySeconds: Int64 = 5,
        clock: @escaping () -> Int64 = { Int64(Date().timeIntervalSince1970) }
    ) {
        self.algorithm = algorithm
        self.issuer = issuer
        self.hsKey = hsKey
        self.rsPublicKey = rsPublicKey
        self.revocationList = revocationList
        self.leewaySeconds = leewaySeconds
        self.clock = clock
    }

    /// Verify `token`. If `requestedExecutionId` is non-nil and the token
    /// is bound to a different execution, throws `ConsentError.invalidToken`.
    public func verify(
        _ token: String,
        requestedExecutionId: String? = nil
    ) throws -> Scope {
        let parsed = try JWT.parse(token)

        // Algorithm check from header.
        guard let alg = parsed.header["alg"] as? String else {
            throw ConsentError.invalidToken(reason: "missing algorithm")
        }
        guard alg == algorithm.rawValue else {
            throw ConsentError.invalidToken(reason: "unexpected algorithm: \(alg)")
        }

        // Signature.
        let valid = try JWT.verifySignature(
            parsed,
            algorithm: algorithm,
            hsKey: hsKey,
            rsPublicKey: rsPublicKey)
        guard valid else {
            throw ConsentError.invalidToken(reason: "signature verification failed")
        }

        let claims = parsed.claims
        for req in ["exp", "iat", "iss", "sub", "jti"] {
            if claims[req] == nil {
                throw ConsentError.invalidToken(reason: "missing required claim: \(req)")
            }
        }

        guard let iss = claims["iss"] as? String, iss == issuer else {
            let got = (claims["iss"] as? String) ?? "<missing>"
            throw ConsentError.invalidToken(
                reason: "iss mismatch: got \(got), want \(issuer)")
        }

        let exp = numericClaim(claims["exp"]) ?? 0
        let now = clock()
        if exp + leewaySeconds < now {
            throw ConsentError.expiredToken
        }

        let jti = (claims["jti"] as? String) ?? ""
        if let rl = revocationList, rl.isRevoked(jti) {
            throw ConsentError.revokedToken(jti: jti)
        }

        let tokenExec = claims["execution_id"] as? String
        if let req = requestedExecutionId, let bound = tokenExec, bound != req {
            throw ConsentError.invalidToken(
                reason: "token bound to \(bound), requested \(req)")
        }

        let subject = (claims["sub"] as? String) ?? ""
        let iat = numericClaim(claims["iat"]) ?? 0
        let scopes = (claims["scopes"] as? [String]) ?? []
        var metadata: [String: String] = [:]
        if let m = claims["metadata"] as? [String: Any] {
            for (k, v) in m {
                if let s = v as? String { metadata[k] = s }
            }
        }
        return Scope(
            token: token,
            subject: subject,
            scopes: scopes,
            executionId: tokenExec,
            jti: jti,
            issuedAt: iat,
            expiresAt: exp,
            metadata: metadata)
    }

    private func numericClaim(_ v: Any?) -> Int64? {
        if let n = v as? NSNumber { return n.int64Value }
        if let i = v as? Int64 { return i }
        if let i = v as? Int { return Int64(i) }
        if let d = v as? Double { return Int64(d) }
        return nil
    }
}
