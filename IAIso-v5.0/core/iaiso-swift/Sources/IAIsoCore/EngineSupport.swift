import Foundation
import IAIsoAudit

/// A single step's worth of work.
public struct StepInput: Sendable, Equatable {
    public var tokens: Int64
    public var toolCalls: Int64
    public var depth: Int64
    public var tag: String?

    public init(tokens: Int64 = 0, toolCalls: Int64 = 0, depth: Int64 = 0, tag: String? = nil) {
        // A negative count would lower pressure. `precondition` is checked in
        // debug and -O release builds (not -Ounchecked), so this fails closed.
        precondition(tokens >= 0, "StepInput.tokens must be >= 0")
        precondition(toolCalls >= 0, "StepInput.toolCalls must be >= 0")
        precondition(depth >= 0, "StepInput.depth must be >= 0")
        self.tokens = tokens
        self.toolCalls = toolCalls
        self.depth = depth
        self.tag = tag
    }

    public static let empty = StepInput()

    public enum DecodeError: Error, Equatable {
        case invalid(String)
    }

    /// Build from untrusted JSON bytes (snake_case keys) without trapping.
    /// `JSONDecoder` refuses fractional, boolean, string and null values for
    /// Int64 fields; negatives and unknown keys are refused here.
    public static func fromJSON(_ data: Data) throws -> StepInput {
        let w = try JSONDecoder().decode(Wire.self, from: data)
        for (name, v) in [("tokens", w.tokens), ("tool_calls", w.toolCalls), ("depth", w.depth)] {
            if let v, v < 0 { throw DecodeError.invalid("StepInput.\(name) must be >= 0") }
        }
        return StepInput(tokens: w.tokens ?? 0, toolCalls: w.toolCalls ?? 0, depth: w.depth ?? 0, tag: w.tag)
    }

    private struct Wire: Decodable {
        let tokens: Int64?
        let toolCalls: Int64?
        let depth: Int64?
        let tag: String?

        enum CodingKeys: String, CodingKey, CaseIterable {
            case tokens, toolCalls = "tool_calls", depth, tag
        }

        init(from decoder: Decoder) throws {
            let c = try decoder.container(keyedBy: AnyKey.self)
            for k in c.allKeys where CodingKeys(rawValue: k.stringValue) == nil {
                throw DecodeError.invalid("StepInput: unknown field \(k.stringValue)")
            }
            func count(_ key: String) throws -> Int64? {
                let k = AnyKey(stringValue: key)!
                guard c.contains(k) else { return nil }
                if try c.decodeNil(forKey: k) { throw DecodeError.invalid("StepInput.\(key) must not be null") }
                return try c.decode(Int64.self, forKey: k)
            }
            tokens = try count("tokens")
            toolCalls = try count("tool_calls")
            depth = try count("depth")
            tag = try c.decodeIfPresent(String.self, forKey: AnyKey(stringValue: "tag")!)
        }
    }

    private struct AnyKey: CodingKey {
        var stringValue: String
        var intValue: Int? { nil }
        init?(stringValue: String) { self.stringValue = stringValue }
        init?(intValue: Int) { return nil }
    }
}

/// Read-only snapshot of engine state.
public struct PressureSnapshot: Sendable, Equatable {
    public let pressure: Double
    public let step: Int64
    public let lifecycle: Lifecycle
    public let lastStepAt: Double

    public init(pressure: Double, step: Int64, lifecycle: Lifecycle, lastStepAt: Double) {
        self.pressure = pressure
        self.step = step
        self.lifecycle = lifecycle
        self.lastStepAt = lastStepAt
    }
}

/// Options for `PressureEngine` and `BoundedExecution`.
public struct EngineOptions: Sendable {
    public var executionId: String
    public var auditSink: Sink
    public var clock: Clock
    public var timestampClock: Clock

    public init(
        executionId: String,
        auditSink: Sink = NullSink.shared,
        clock: Clock = WallClock.shared,
        timestampClock: Clock? = nil
    ) {
        self.executionId = executionId
        self.auditSink = auditSink
        self.clock = clock
        self.timestampClock = timestampClock ?? clock
    }
}
