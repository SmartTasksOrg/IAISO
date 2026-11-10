import Foundation

/// Base64url encoding helpers (no padding) per RFC 7515.
public enum Base64URL {

    /// Encode bytes as base64url, no padding.
    public static func encode(_ data: Data) -> String {
        var s = data.base64EncodedString()
        s = s.replacingOccurrences(of: "+", with: "-")
        s = s.replacingOccurrences(of: "/", with: "_")
        // Strip padding.
        while s.hasSuffix("=") { s.removeLast() }
        return s
    }

    /// Decode a base64url string. Accepts with or without padding.
    public static func decode(_ s: String) throws -> Data {
        var t = s.replacingOccurrences(of: "-", with: "+")
        t = t.replacingOccurrences(of: "_", with: "/")
        // Pad to a multiple of 4.
        let rem = t.count % 4
        if rem > 0 {
            t += String(repeating: "=", count: 4 - rem)
        }
        guard let d = Data(base64Encoded: t) else {
            throw ConsentError.invalidToken(reason: "malformed base64url segment")
        }
        return d
    }
}
