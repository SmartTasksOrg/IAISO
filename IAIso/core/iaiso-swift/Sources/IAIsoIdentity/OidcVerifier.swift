import Foundation
import IAIsoConsent

#if canImport(Security)
import Security
#endif

/// IAIso OIDC identity verifier.
///
/// This class is HTTP-free. The caller fetches JWKS bytes (using
/// URLSession, Alamofire, or any HTTP library) and passes them to
/// `setJwksFromBytes(_:)`. This keeps the SDK dependency-light and lets
/// users use whichever HTTP client they prefer.
public final class OidcVerifier: @unchecked Sendable {
    public let config: ProviderConfig
    private var jwks: Jwks?
    private let lock = NSLock()
    private let clock: () -> Int64

    public init(
        config: ProviderConfig,
        clock: @escaping () -> Int64 = { Int64(Date().timeIntervalSince1970) }
    ) {
        self.config = config
        self.clock = clock
    }

    /// Inject pre-fetched JWKS bytes into the verifier's cache.
    public func setJwksFromBytes(_ body: Data) throws {
        let root = try JSONSerialization.jsonObject(with: body)
        guard let map = root as? [String: Any],
              let arr = map["keys"] as? [Any] else {
            throw IdentityError("JWKS missing keys array")
        }
        var keys: [Jwk] = []
        for k in arr {
            guard let m = k as? [String: Any] else { continue }
            keys.append(Jwk(
                kty: (m["kty"] as? String) ?? "",
                kid: m["kid"] as? String,
                alg: m["alg"] as? String,
                use: m["use"] as? String,
                n: m["n"] as? String,
                e: m["e"] as? String))
        }
        lock.lock()
        jwks = Jwks(keys: keys)
        lock.unlock()
    }

    /// Verify a token against the cached JWKS.
    /// - Returns: the verified claims as a dictionary.
    public func verify(_ token: String) throws -> [String: Any] {
        lock.lock()
        guard let jwks = jwks else {
            lock.unlock()
            throw IdentityError("oidc: JWKS not loaded; call setJwksFromBytes first")
        }
        lock.unlock()

        let parts = token.split(separator: ".", omittingEmptySubsequences: false)
        guard parts.count == 3 else {
            throw IdentityError("oidc: malformed JWT")
        }
        let signingInput = String(parts[0]) + "." + String(parts[1])
        let signature: Data
        let header: [String: Any]
        let claims: [String: Any]
        do {
            let headerData = try Base64URL.decode(String(parts[0]))
            let claimsData = try Base64URL.decode(String(parts[1]))
            signature = try Base64URL.decode(String(parts[2]))
            header = (try JSONSerialization.jsonObject(with: headerData)) as? [String: Any] ?? [:]
            claims = (try JSONSerialization.jsonObject(with: claimsData)) as? [String: Any] ?? [:]
        } catch {
            throw IdentityError("oidc: malformed JWT JSON")
        }

        let alg = (header["alg"] as? String) ?? ""
        guard config.allowedAlgorithms.contains(alg) else {
            throw IdentityError("oidc: algorithm not allowed: \(alg)")
        }
        let kid = (header["kid"] as? String) ?? ""

        // Find matching key.
        var match: Jwk?
        for k in jwks.keys {
            if k.kid == kid { match = k; break }
        }
        if match == nil, jwks.keys.count == 1, kid.isEmpty {
            match = jwks.keys[0]
        }
        guard let jwk = match else {
            throw IdentityError("oidc: kid \(kid) not found in JWKS")
        }
        guard jwk.kty == "RSA" else {
            throw IdentityError("oidc: unsupported key type: \(jwk.kty)")
        }

        // Verify signature.
        guard let signingBytes = signingInput.data(using: .utf8) else {
            throw IdentityError("oidc: encoding failed")
        }
        let pemData = try Self.rsaPublicKeyPEM(nB64: jwk.n ?? "", eB64: jwk.e ?? "")
        let valid = try JWT.rsaVerifySha256(
            message: signingBytes, signature: signature, publicKey: pemData)
        guard valid else {
            throw IdentityError("oidc: signature verification failed")
        }

        // Issuer.
        if let want = config.issuer, !want.isEmpty {
            let got = (claims["iss"] as? String) ?? ""
            guard got == want else {
                throw IdentityError("oidc: iss mismatch: got \(got), want \(want)")
            }
        }
        // Expiry.
        if let exp = numericClaim(claims["exp"]) {
            let now = clock()
            if exp + config.leewaySeconds < now {
                throw IdentityError("oidc: token expired")
            }
        }
        // Audience.
        if let want = config.audience, !want.isEmpty {
            guard Self.audienceMatches(claims["aud"], want: want) else {
                throw IdentityError("oidc: aud mismatch (expected \(want))")
            }
        }
        return claims
    }

    /// Convert verified claims into a deduplicated list of IAIso scopes.
    public static func deriveScopes(_ claims: [String: Any], mapping: ScopeMapping) -> [String] {
        let directClaims = mapping.directClaims.isEmpty
            ? ["scp", "scope", "permissions"]
            : mapping.directClaims

        var seen: Set<String> = []
        for c in directClaims {
            guard let val = claims[c] else { continue }
            if let s = val as? String {
                let parts = s.split(whereSeparator: { $0 == " " || $0 == "," || $0 == "\t" })
                for p in parts where !p.isEmpty {
                    seen.insert(String(p))
                }
            } else if let arr = val as? [Any] {
                for item in arr {
                    if let s = item as? String { seen.insert(s) }
                }
            }
        }
        var groups: [String] = []
        for c in ["groups", "roles"] {
            if let arr = claims[c] as? [Any] {
                for g in arr { if let s = g as? String { groups.append(s) } }
            }
        }
        for g in groups {
            if let scopes = mapping.groupToScopes[g] {
                for s in scopes { seen.insert(s) }
            }
        }
        for s in mapping.alwaysGrant { seen.insert(s) }
        return Array(seen).sorted()
    }

    /// Mint an IAIso consent scope from a verified OIDC identity.
    public static func issueFromOidc(
        verifier: OidcVerifier,
        issuer: Issuer,
        token: String,
        mapping: ScopeMapping,
        ttlSeconds: Int64 = 3600,
        executionId: String? = nil
    ) throws -> Scope {
        let claims = try verifier.verify(token)
        let subject = (claims["sub"] as? String) ?? "unknown"
        let scopes = deriveScopes(claims, mapping: mapping)

        var metadata: [String: Any] = [:]
        for (src, dst) in [("iss", "oidc_iss"), ("jti", "oidc_jti"), ("aud", "oidc_aud")] {
            if let v = claims[src] { metadata[dst] = v }
        }
        return try issuer.issue(
            subject: subject,
            scopes: scopes,
            executionId: executionId,
            ttlSeconds: ttlSeconds,
            metadata: metadata.isEmpty ? nil : metadata)
    }

    // MARK: - Internals

    private func numericClaim(_ v: Any?) -> Int64? {
        if let n = v as? NSNumber { return n.int64Value }
        if let i = v as? Int64 { return i }
        if let i = v as? Int { return Int64(i) }
        if let d = v as? Double { return Int64(d) }
        return nil
    }

    private static func audienceMatches(_ aud: Any?, want: String) -> Bool {
        if aud == nil { return false }
        if let s = aud as? String { return s == want }
        if let arr = aud as? [Any] {
            for a in arr {
                if let s = a as? String, s == want { return true }
            }
        }
        return false
    }

    /// Build an RSA public key PEM from base64url-encoded modulus and
    /// exponent (per RFC 7517).
    static func rsaPublicKeyPEM(nB64: String, eB64: String) throws -> Data {
        let n = try Base64URL.decode(nB64)
        let e = try Base64URL.decode(eB64)

        let modulus = asn1Integer(n)
        let exponent = asn1Integer(e)
        let rsaSeq = asn1Sequence(modulus + exponent)

        // SubjectPublicKeyInfo:
        //   SEQUENCE { algorithm SEQUENCE { OID rsaEncryption, NULL },
        //              BIT STRING { rsaSeq } }
        var rsaOid = Data()
        rsaOid.append(contentsOf: [0x06, 0x09,
            0x2a, 0x86, 0x48, 0x86, 0xf7, 0x0d, 0x01, 0x01, 0x01])
        let algId = asn1Sequence(rsaOid + Data([0x05, 0x00]))
        var bitString = Data([0x00])  // unused-bits prefix
        bitString.append(rsaSeq)
        let spkBitString = asn1Tag(0x03, bitString)
        let spki = asn1Sequence(algId + spkBitString)

        // PEM-encode for SecKeyCreateWithData (it accepts raw DER, but we
        // wrap as PEM for cross-platform parsing in JWT.parsePublicKey).
        let b64 = spki.base64EncodedString()
        let chunks = stride(from: 0, to: b64.count, by: 64).map { i -> String in
            let start = b64.index(b64.startIndex, offsetBy: i)
            let end = b64.index(start, offsetBy: min(64, b64.count - i))
            return String(b64[start..<end])
        }
        let pem = "-----BEGIN PUBLIC KEY-----\n"
            + chunks.joined(separator: "\n")
            + "\n-----END PUBLIC KEY-----\n"
        guard let data = pem.data(using: .utf8) else {
            throw IdentityError("oidc: PEM encoding failed")
        }
        return data
    }

    private static func asn1Integer(_ bytes: Data) -> Data {
        var b = bytes
        if !b.isEmpty, (b[0] & 0x80) != 0 {
            b.insert(0x00, at: 0)
        }
        return asn1Tag(0x02, b)
    }

    private static func asn1Sequence(_ contents: Data) -> Data {
        return asn1Tag(0x30, contents)
    }

    private static func asn1Tag(_ tag: UInt8, _ contents: Data) -> Data {
        var out = Data([tag])
        let len = contents.count
        if len < 0x80 {
            out.append(UInt8(len))
        } else {
            var lenBytes: [UInt8] = []
            var tmp = len
            while tmp > 0 {
                lenBytes.insert(UInt8(tmp & 0xff), at: 0)
                tmp >>= 8
            }
            out.append(0x80 | UInt8(lenBytes.count))
            out.append(contentsOf: lenBytes)
        }
        out.append(contents)
        return out
    }
}
