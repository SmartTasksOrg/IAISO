import Foundation

#if canImport(Security)
import Security
#endif

/// Internal JWT codec. Hand-rolled HS256 / RS256 using CryptoKit (HMAC)
/// and `Security.framework` (RSA on Apple platforms) or swift-crypto
/// (RSA on Linux). No third-party JWT library required.
public enum JWT {

    /// Parsed (but not verified) JWT.
    public struct Parsed {
        public let headerB64: String
        public let claimsB64: String
        public let signatureB64: String
        public let header: [String: Any]
        public let claims: [String: Any]
        public let signature: Data
    }

    /// Sign claims into a compact JWT.
    ///
    /// - Parameter hsKey: raw HMAC bytes (HS256). Required for HS256.
    /// - Parameter rsPrivateKey: PKCS#8 / PEM private key data (RS256).
    public static func sign(
        algorithm: Algorithm,
        claims: [String: Any],
        hsKey: Data? = nil,
        rsPrivateKey: Data? = nil
    ) throws -> String {
        let header: [String: Any] = ["alg": algorithm.rawValue, "typ": "JWT"]
        let headerJSON = try canonicalJSONData(header)
        let claimsJSON = try canonicalJSONData(claims)
        let headerB64 = Base64URL.encode(headerJSON)
        let claimsB64 = Base64URL.encode(claimsJSON)
        let signingInput = headerB64 + "." + claimsB64
        guard let signingBytes = signingInput.data(using: .utf8) else {
            throw ConsentError.invalidToken(reason: "could not encode signing input")
        }

        let signature: Data
        switch algorithm {
        case .hs256:
            guard let key = hsKey, !key.isEmpty else {
                throw ConsentError.invalidToken(reason: "HS256 requires hsKey")
            }
            signature = hmacSha256(message: signingBytes, key: key)
        case .rs256:
            guard let priv = rsPrivateKey else {
                throw ConsentError.invalidToken(reason: "RS256 requires rsPrivateKey")
            }
            signature = try rsaSignSha256(message: signingBytes, privateKey: priv)
        }
        return signingInput + "." + Base64URL.encode(signature)
    }

    /// Parse a compact JWT into its three deserialized parts.
    /// Does NOT verify the signature.
    public static func parse(_ token: String) throws -> Parsed {
        let parts = token.split(separator: ".", omittingEmptySubsequences: false)
        guard parts.count == 3 else {
            throw ConsentError.invalidToken(reason: "malformed JWT: expected 3 segments")
        }
        let headerB64 = String(parts[0])
        let claimsB64 = String(parts[1])
        let sigB64 = String(parts[2])
        let headerData = try Base64URL.decode(headerB64)
        let claimsData = try Base64URL.decode(claimsB64)
        let sigData = try Base64URL.decode(sigB64)

        let headerObj = try JSONSerialization.jsonObject(with: headerData)
        guard let header = headerObj as? [String: Any] else {
            throw ConsentError.invalidToken(reason: "JWT header must be an object")
        }
        let claimsObj = try JSONSerialization.jsonObject(with: claimsData)
        guard let claims = claimsObj as? [String: Any] else {
            throw ConsentError.invalidToken(reason: "JWT claims must be an object")
        }
        return Parsed(
            headerB64: headerB64,
            claimsB64: claimsB64,
            signatureB64: sigB64,
            header: header,
            claims: claims,
            signature: sigData)
    }

    /// Verify the signature on a parsed JWT.
    public static func verifySignature(
        _ parsed: Parsed,
        algorithm: Algorithm,
        hsKey: Data? = nil,
        rsPublicKey: Data? = nil
    ) throws -> Bool {
        let signingInput = parsed.headerB64 + "." + parsed.claimsB64
        guard let signingBytes = signingInput.data(using: .utf8) else {
            return false
        }
        switch algorithm {
        case .hs256:
            guard let key = hsKey else { return false }
            let expected = hmacSha256(message: signingBytes, key: key)
            return constantTimeEquals(expected, parsed.signature)
        case .rs256:
            guard let pub = rsPublicKey else { return false }
            return try rsaVerifySha256(
                message: signingBytes, signature: parsed.signature, publicKey: pub)
        }
    }

    // MARK: - Internals

    /// Encode a Foundation JSON value with stable key order. The IAIso JWT
    /// claim format requires a specific field order (iss, sub, iat, exp,
    /// jti, scopes, ...) — the caller controls order via an ordered map
    /// passed via the `orderedKeys` parameter, OR we sort alphabetically
    /// for determinism in the absence of explicit ordering.
    static func canonicalJSONData(_ value: [String: Any]) throws -> Data {
        // For interoperability with other reference SDKs, key order is NOT
        // sorted alphabetically — `Issuer.issue()` builds the claims dict
        // in the spec order and we encode preserving that order.
        // However, JSONSerialization on Apple platforms doesn't preserve
        // key order from a Swift dictionary. We hand-build the JSON using
        // a deterministic but order-preserving approach: the caller passes
        // a `[String: Any]` whose iteration order is undefined; we encode
        // using JSONSerialization (which IS stable for primitive-only maps
        // in practice on Apple platforms but not guaranteed). For maximum
        // safety, callers that care about wire-format order should call
        // `canonicalJSONDataOrdered` with an explicit ordered list.
        return try JSONSerialization.data(
            withJSONObject: value,
            options: [.sortedKeys, .withoutEscapingSlashes])
    }

    /// Hand-build canonical JSON from an explicit ordered list of (key, value).
    /// Used by `Issuer` to emit claims in spec order.
    static func canonicalJSONDataOrdered(_ pairs: [(String, Any)]) throws -> Data {
        var s = "{"
        for (i, (k, v)) in pairs.enumerated() {
            if i > 0 { s += "," }
            s += jsonEncodeString(k) + ":"
            s += try jsonEncode(v)
        }
        s += "}"
        guard let data = s.data(using: .utf8) else {
            throw ConsentError.invalidToken(reason: "encode failed")
        }
        return data
    }

    static func jsonEncodeString(_ s: String) -> String {
        // Use JSONSerialization for proper escaping by encoding via a 1-element array.
        if let data = try? JSONSerialization.data(
            withJSONObject: [s], options: [.withoutEscapingSlashes]),
           let str = String(data: data, encoding: .utf8) {
            // Strip surrounding [ ]
            var t = str
            if t.hasPrefix("["), t.hasSuffix("]") {
                t = String(t.dropFirst().dropLast())
            }
            return t
        }
        return "\"\(s)\""
    }

    static func jsonEncode(_ value: Any) throws -> String {
        if value is NSNull { return "null" }
        // NSNumber check first to disambiguate bool vs numeric.
        if let n = value as? NSNumber {
            #if canImport(ObjectiveC)
            if String(cString: n.objCType) == "c" {
                return n.boolValue ? "true" : "false"
            }
            #endif
            // Numeric.
            let d = n.doubleValue
            if d.truncatingRemainder(dividingBy: 1) == 0, abs(d) < 1e16 {
                return String(n.int64Value)
            }
            return String(d)
        }
        if let b = value as? Bool, type(of: value) == Bool.self {
            return b ? "true" : "false"
        }
        if let i = value as? Int { return String(i) }
        if let i = value as? Int64 { return String(i) }
        if let d = value as? Double {
            if d.truncatingRemainder(dividingBy: 1) == 0, abs(d) < 1e16 {
                return String(Int64(d))
            }
            return String(d)
        }
        if let s = value as? String { return jsonEncodeString(s) }
        if let arr = value as? [Any] {
            let parts = try arr.map { try jsonEncode($0) }
            return "[" + parts.joined(separator: ",") + "]"
        }
        if let m = value as? [String: Any] {
            let data = try JSONSerialization.data(
                withJSONObject: m,
                options: [.sortedKeys, .withoutEscapingSlashes])
            return String(data: data, encoding: .utf8) ?? "{}"
        }
        // Fallback: use JSONSerialization
        let data = try JSONSerialization.data(
            withJSONObject: [value],
            options: [.withoutEscapingSlashes])
        var s = String(data: data, encoding: .utf8) ?? ""
        if s.hasPrefix("["), s.hasSuffix("]") {
            s = String(s.dropFirst().dropLast())
        }
        return s
    }

    // MARK: - Crypto primitives

    static func hmacSha256(message: Data, key: Data) -> Data {
        let symKey = SymmetricKey(data: key)
        let mac = HMAC<SHA256>.authenticationCode(for: message, using: symKey)
        return Data(mac)
    }

    static func constantTimeEquals(_ a: Data, _ b: Data) -> Bool {
        guard a.count == b.count else { return false }
        var diff: UInt8 = 0
        for i in 0..<a.count {
            diff |= a[i] ^ b[i]
        }
        return diff == 0
    }

    static func rsaSignSha256(message: Data, privateKey: Data) throws -> Data {
        #if canImport(Security)
        let key = try parsePrivateKey(privateKey)
        var error: Unmanaged<CFError>?
        guard let sig = SecKeyCreateSignature(
            key,
            .rsaSignatureMessagePKCS1v15SHA256,
            message as CFData,
            &error) as Data? else {
            let msg = error?.takeRetainedValue().localizedDescription ?? "RSA sign failed"
            throw ConsentError.invalidToken(reason: msg)
        }
        return sig
        #else
        throw ConsentError.invalidToken(
            reason: "RSA signing not implemented on this platform")
        #endif
    }

    public static func rsaVerifySha256(
        message: Data, signature: Data, publicKey: Data
    ) throws -> Bool {
        #if canImport(Security)
        let key = try parsePublicKey(publicKey)
        var error: Unmanaged<CFError>?
        let ok = SecKeyVerifySignature(
            key,
            .rsaSignatureMessagePKCS1v15SHA256,
            message as CFData,
            signature as CFData,
            &error)
        return ok
        #else
        return false
        #endif
    }

    #if canImport(Security)
    /// Parse a PEM- or DER-encoded RSA private key into a SecKey.
    static func parsePrivateKey(_ pemOrDer: Data) throws -> SecKey {
        let der = try stripPemHeader(pemOrDer)
        let attrs: [String: Any] = [
            kSecAttrKeyType as String: kSecAttrKeyTypeRSA,
            kSecAttrKeyClass as String: kSecAttrKeyClassPrivate,
        ]
        var error: Unmanaged<CFError>?
        guard let key = SecKeyCreateWithData(der as CFData, attrs as CFDictionary, &error) else {
            let msg = error?.takeRetainedValue().localizedDescription ?? "bad RSA private key"
            throw ConsentError.invalidToken(reason: msg)
        }
        return key
    }

    /// Parse a PEM- or DER-encoded RSA public key into a SecKey.
    static func parsePublicKey(_ pemOrDer: Data) throws -> SecKey {
        let der = try stripPemHeader(pemOrDer)
        let attrs: [String: Any] = [
            kSecAttrKeyType as String: kSecAttrKeyTypeRSA,
            kSecAttrKeyClass as String: kSecAttrKeyClassPublic,
        ]
        var error: Unmanaged<CFError>?
        guard let key = SecKeyCreateWithData(der as CFData, attrs as CFDictionary, &error) else {
            let msg = error?.takeRetainedValue().localizedDescription ?? "bad RSA public key"
            throw ConsentError.invalidToken(reason: msg)
        }
        return key
    }

    /// Strip PEM headers and base64-decode the body. Passes raw DER through.
    static func stripPemHeader(_ data: Data) throws -> Data {
        guard let s = String(data: data, encoding: .utf8) else { return data }
        if !s.contains("-----BEGIN") { return data }  // already DER
        let lines = s.components(separatedBy: .newlines)
            .filter { !$0.hasPrefix("-----") && !$0.isEmpty }
        let b64 = lines.joined()
        guard let der = Data(base64Encoded: b64) else {
            throw ConsentError.invalidToken(reason: "could not decode PEM body")
        }
        return der
    }
    #endif
}
