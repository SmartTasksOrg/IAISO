import Foundation
import IAIsoAudit

/// High-level execution facade. Composes a `PressureEngine` with an
/// audit sink and lifecycle management.
///
/// Use `BoundedExecution.run(_:body:)` for closure-style with automatic
/// cleanup, or `start(_:)` + manual `close()` for explicit control.
public final class BoundedExecution: @unchecked Sendable {

    public struct Options: Sendable {
        public var executionId: String?
        public var config: PressureConfig
        public var auditSink: Sink
        public var clock: Clock
        public var timestampClock: Clock?

        public init(
            executionId: String? = nil,
            config: PressureConfig = .defaults,
            auditSink: Sink = NullSink.shared,
            clock: Clock = WallClock.shared,
            timestampClock: Clock? = nil
        ) {
            self.executionId = executionId
            self.config = config
            self.auditSink = auditSink
            self.clock = clock
            self.timestampClock = timestampClock
        }
    }

    public let engine: PressureEngine
    private let auditSink: Sink
    private let timestampClock: Clock
    private let lock = NSLock()
    private var _closed = false

    private init(_ options: Options) throws {
        let execId = options.executionId.flatMap { $0.isEmpty ? nil : $0 }
            ?? "exec-\(Self.randomHex(6))"
        let tsClock = options.timestampClock ?? options.clock
        self.auditSink = options.auditSink
        self.timestampClock = tsClock
        self.engine = try PressureEngine(
            config: options.config,
            options: EngineOptions(
                executionId: execId,
                auditSink: options.auditSink,
                clock: options.clock,
                timestampClock: tsClock))
    }

    /// Construct a `BoundedExecution`. The caller MUST `close()` it.
    public static func start(_ options: Options = Options()) throws -> BoundedExecution {
        return try BoundedExecution(options)
    }

    /// Run a closure inside a bounded execution; closes on exit.
    public static func run(
        _ options: Options = Options(),
        body: (BoundedExecution) throws -> Void
    ) throws {
        let exec = try start(options)
        var errored = false
        do {
            try body(exec)
        } catch {
            errored = true
            exec.closeWith(errored: true)
            throw error
        }
        exec.closeWith(errored: errored)
    }

    public func snapshot() -> PressureSnapshot { engine.snapshot() }

    /// Account for tokens with an optional tag.
    @discardableResult
    public func recordTokens(_ tokens: Int64, tag: String? = nil) -> StepOutcome {
        return engine.step(StepInput(tokens: tokens, tag: tag))
    }

    /// Account for a single tool invocation.
    @discardableResult
    public func recordToolCall(_ name: String, tokens: Int64 = 0) -> StepOutcome {
        return engine.step(StepInput(tokens: tokens, toolCalls: 1, tag: name))
    }

    /// General step accounting.
    @discardableResult
    public func recordStep(_ work: StepInput) -> StepOutcome {
        return engine.step(work)
    }

    /// Pre-check the engine state without advancing it.
    public func check() -> StepOutcome {
        switch engine.lifecycle {
        case .locked: return .locked
        case .escalated: return .escalated
        default: return .ok
        }
    }

    @discardableResult
    public func reset() -> PressureSnapshot { engine.reset() }

    /// Close the execution, emitting `execution.closed`. Idempotent.
    public func close() {
        closeWith(errored: false)
    }

    private func closeWith(errored: Bool) {
        lock.lock()
        if _closed {
            lock.unlock()
            return
        }
        _closed = true
        lock.unlock()
        let snap = engine.snapshot()
        auditSink.emit(Event(
            executionId: engine.executionId,
            kind: "execution.closed",
            timestamp: timestampClock.now(),
            data: [
                "final_pressure": .double(snap.pressure),
                "final_lifecycle": .string(snap.lifecycle.rawValue),
                "exception": errored ? .string("error") : .null,
            ]))
    }

    deinit {
        // Defensive: guarantee close is emitted even if user forgot.
        closeWith(errored: false)
    }

    private static func randomHex(_ bytes: Int) -> String {
        var data = Data(count: bytes)
        for i in 0..<bytes {
            data[i] = UInt8.random(in: 0...UInt8.max)
        }
        return data.map { String(format: "%02x", $0) }.joined()
    }
}
