import Foundation

/// Type-safe sum of all JSON value kinds. Used as the value type for
/// {@link Event#data} and for JSON parsing across the SDK.
///
/// Use the `.literal*` static helpers or the convenience initializers
/// (`AnyJSON(42)`, `AnyJSON("foo")`) for ergonomic construction.
public enum AnyJSON: Sendable, Equatable {
    case null
    case bool(Bool)
    case int(Int64)
    case double(Double)
    case string(String)
    indirect case array([AnyJSON])
    indirect case object([String: AnyJSON])

    // Convenience initializers
    public init(_ value: Bool)            { self = .bool(value) }
    public init(_ value: Int)             { self = .int(Int64(value)) }
    public init(_ value: Int64)           { self = .int(value) }
    public init(_ value: Double)          { self = .double(value) }
    public init(_ value: String)          { self = .string(value) }
    public init(_ value: [AnyJSON])       { self = .array(value) }
    public init(_ value: [String: AnyJSON]) { self = .object(value) }

    /// Build from `Foundation.JSONSerialization` output.
    public static func from(_ raw: Any?) -> AnyJSON {
        guard let raw = raw else { return .null }
        if raw is NSNull { return .null }
        // NSNumber check first because Bool is bridged to NSNumber on Apple.
        // We must inspect objCType to distinguish bool from numeric.
        if let n = raw as? NSNumber {
            #if canImport(ObjectiveC)
            let t = String(cString: n.objCType)
            switch t {
            case "c": return .bool(n.boolValue)         // BOOL
            case "f", "d": return .double(n.doubleValue) // float / double
            default: return .int(n.int64Value)          // any integer width
            }
            #else
            // On corelibs-foundation (Linux) Bool is its own type, not bridged.
            if let b = raw as? Bool, type(of: raw) == Bool.self { return .bool(b) }
            if let i = raw as? Int64 { return .int(i) }
            if let i = raw as? Int { return .int(Int64(i)) }
            if let d = raw as? Double { return .double(d) }
            return .double(n.doubleValue)
            #endif
        }
        if let b = raw as? Bool, type(of: raw) == Bool.self { return .bool(b) }
        if let i = raw as? Int { return .int(Int64(i)) }
        if let i = raw as? Int64 { return .int(i) }
        if let d = raw as? Double { return .double(d) }
        if let s = raw as? String { return .string(s) }
        if let a = raw as? [Any?] {
            return .array(a.map { AnyJSON.from($0) })
        }
        if let a = raw as? [Any] {
            return .array(a.map { AnyJSON.from($0) })
        }
        if let m = raw as? [String: Any?] {
            var out: [String: AnyJSON] = [:]
            for (k, v) in m { out[k] = AnyJSON.from(v) }
            return .object(out)
        }
        if let m = raw as? [String: Any] {
            var out: [String: AnyJSON] = [:]
            for (k, v) in m { out[k] = AnyJSON.from(v) }
            return .object(out)
        }
        // Unknown type — best-effort string fallback.
        return .string(String(describing: raw))
    }

    /// Type-narrowing accessors.
    public var stringValue: String? {
        if case .string(let s) = self { return s }
        return nil
    }
    public var intValue: Int64? {
        if case .int(let i) = self { return i }
        if case .double(let d) = self, d.truncatingRemainder(dividingBy: 1) == 0,
           abs(d) < 1e16 {
            return Int64(d)
        }
        return nil
    }
    public var doubleValue: Double? {
        if case .double(let d) = self { return d }
        if case .int(let i) = self { return Double(i) }
        return nil
    }
    public var boolValue: Bool? {
        if case .bool(let b) = self { return b }
        return nil
    }
    public var arrayValue: [AnyJSON]? {
        if case .array(let a) = self { return a }
        return nil
    }
    public var objectValue: [String: AnyJSON]? {
        if case .object(let o) = self { return o }
        return nil
    }
    public var isNumber: Bool {
        switch self {
        case .int, .double: return true
        default: return false
        }
    }
}

extension AnyJSON: ExpressibleByNilLiteral {
    public init(nilLiteral: ()) { self = .null }
}

extension AnyJSON: ExpressibleByBooleanLiteral {
    public init(booleanLiteral value: Bool) { self = .bool(value) }
}

extension AnyJSON: ExpressibleByIntegerLiteral {
    public init(integerLiteral value: Int64) { self = .int(value) }
}

extension AnyJSON: ExpressibleByFloatLiteral {
    public init(floatLiteral value: Double) { self = .double(value) }
}

extension AnyJSON: ExpressibleByStringLiteral {
    public init(stringLiteral value: String) { self = .string(value) }
}

extension AnyJSON: ExpressibleByArrayLiteral {
    public init(arrayLiteral elements: AnyJSON...) { self = .array(elements) }
}

extension AnyJSON: ExpressibleByDictionaryLiteral {
    public init(dictionaryLiteral elements: (String, AnyJSON)...) {
        var d: [String: AnyJSON] = [:]
        for (k, v) in elements { d[k] = v }
        self = .object(d)
    }
}
