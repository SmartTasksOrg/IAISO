import Foundation

/// IAIso audit event envelope.
///
/// The JSON form of this struct MUST emit fields in spec order:
/// `schema_version`, `execution_id`, `kind`, `timestamp`, `data` —
/// with `data` keys sorted alphabetically. Integer-valued floats
/// serialize as `0` not `0.0` to match the wire format of every
/// other reference SDK.
public struct Event: Sendable {
    public static let currentSchemaVersion: String = "1.0"

    public let schemaVersion: String
    public let executionId: String
    public let kind: String
    public let timestamp: Double

    /// Data payload. Keys are emitted alphabetically in `toJSON()`.
    /// Values may be `Int`, `Int64`, `Double`, `Bool`, `String`,
    /// `[Any?]`, `[String: Any?]`, or `nil`.
    public let data: [String: AnyJSON]

    public init(
        executionId: String,
        kind: String,
        timestamp: Double,
        data: [String: AnyJSON] = [:],
        schemaVersion: String = Event.currentSchemaVersion
    ) {
        self.executionId = executionId
        self.kind = kind
        self.timestamp = timestamp
        self.data = data
        self.schemaVersion = schemaVersion
    }

    /// Serialize to canonical JSON. Field order is the spec order; `data` keys
    /// are sorted alphabetically; integer-valued floats emit as integers.
    public func toJSON() -> String {
        var s = "{"
        s += "\"schema_version\":" + JSONEncoding.encodeString(schemaVersion)
        s += ",\"execution_id\":" + JSONEncoding.encodeString(executionId)
        s += ",\"kind\":" + JSONEncoding.encodeString(kind)
        s += ",\"timestamp\":" + JSONEncoding.encodeNumber(timestamp)
        s += ",\"data\":" + JSONEncoding.encodeMap(data)
        s += "}"
        return s
    }
}
