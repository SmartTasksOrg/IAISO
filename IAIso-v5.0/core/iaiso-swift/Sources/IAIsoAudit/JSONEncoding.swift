import Foundation

/// Canonical JSON encoding that matches the IAIso wire format.
///
/// Differences from `JSONSerialization`:
///   - Object keys are emitted alphabetically (stable across runs).
///   - Integer-valued floats emit as integers (`0` not `0.0`).
///   - Forward slashes are not escaped (matches the other reference SDKs).
///   - NaN and Infinity emit as `null`.
public enum JSONEncoding {

    /// Encode an `AnyJSON` value to canonical JSON text.
    public static func encode(_ value: AnyJSON) -> String {
        switch value {
        case .null:           return "null"
        case .bool(let b):    return b ? "true" : "false"
        case .int(let i):     return String(i)
        case .double(let d):  return encodeNumber(d)
        case .string(let s):  return encodeString(s)
        case .array(let xs):
            let parts = xs.map { encode($0) }
            return "[" + parts.joined(separator: ",") + "]"
        case .object(let m):  return encodeMap(m)
        }
    }

    /// Encode a `[String: AnyJSON]` with keys sorted alphabetically.
    public static func encodeMap(_ m: [String: AnyJSON]) -> String {
        let keys = m.keys.sorted()
        var parts: [String] = []
        parts.reserveCapacity(keys.count)
        for k in keys {
            parts.append(encodeString(k) + ":" + encode(m[k]!))
        }
        return "{" + parts.joined(separator: ",") + "}"
    }

    /// Encode a string with the standard escapes for `"`, `\`, and the
    /// C0 control range. Forward slashes are NOT escaped.
    public static func encodeString(_ s: String) -> String {
        var out = "\""
        for ch in s.unicodeScalars {
            switch ch {
            case "\"": out += "\\\""
            case "\\": out += "\\\\"
            case "\u{08}": out += "\\b"
            case "\u{09}": out += "\\t"
            case "\u{0A}": out += "\\n"
            case "\u{0C}": out += "\\f"
            case "\u{0D}": out += "\\r"
            default:
                if ch.value < 0x20 {
                    out += String(format: "\\u%04x", ch.value)
                } else {
                    out += String(ch)
                }
            }
        }
        out += "\""
        return out
    }

    /// Encode a number per spec wire format: integer-valued floats emit
    /// as integers; NaN/Infinity emit as `null` (JSON doesn't represent
    /// them); ordinary floats use Swift's default formatting.
    public static func encodeNumber<N: BinaryFloatingPoint>(_ n: N) -> String {
        let d = Double(n)
        if d.isNaN || d.isInfinite { return "null" }
        if d.truncatingRemainder(dividingBy: 1) == 0, abs(d) < 1e16 {
            return String(Int64(d))
        }
        // Use Swift's default formatting; it produces the shortest
        // round-trippable representation for double precision.
        let s = "\(d)"
        // Swift may produce "1e+20" — JSON requires lowercase exponent without "+".
        return s.replacingOccurrences(of: "+", with: "")
    }

    /// Encode an integer.
    public static func encodeInt(_ n: Int64) -> String {
        return String(n)
    }
}
