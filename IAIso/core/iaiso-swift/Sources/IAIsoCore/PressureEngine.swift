import Foundation
import IAIsoAudit

/// The IAIso pressure engine. Tracks accumulated load, decays over time,
/// and emits lifecycle events on threshold crossings.
///
/// See `spec/pressure/README.md` for normative semantics.
///
/// Wire-format events emitted: `engine.init`, `engine.step`,
/// `engine.step.rejected`, `engine.escalation`, `engine.release`,
/// `engine.locked`, `engine.reset`.
public final class PressureEngine: @unchecked Sendable {

    public let config: PressureConfig
    public let executionId: String

    private let audit: Sink
    private let clock: Clock
    private let timestampClock: Clock
    private let lock = NSLock()

    // Mutable state — guarded by `lock`.
    private var _pressure: Double = 0
    private var _stepCount: Int64 = 0
    private var _lifecycle: Lifecycle = .init
    private var _lastStepAt: Double

    public init(config: PressureConfig, options: EngineOptions) throws {
        try config.validate()
        self.config = config
        self.executionId = options.executionId
        self.audit = options.auditSink
        self.clock = options.clock
        self.timestampClock = options.timestampClock
        self._lastStepAt = options.clock.now()
        self.emit(kind: "engine.init", data: ["pressure": .double(0)])
    }

    public var pressure: Double {
        lock.lock(); defer { lock.unlock() }
        return _pressure
    }

    public var lifecycle: Lifecycle {
        lock.lock(); defer { lock.unlock() }
        return _lifecycle
    }

    public func snapshot() -> PressureSnapshot {
        lock.lock(); defer { lock.unlock() }
        return PressureSnapshot(
            pressure: _pressure, step: _stepCount,
            lifecycle: _lifecycle, lastStepAt: _lastStepAt)
    }

    /// Account for a unit of work; advance the engine.
    @discardableResult
    public func step(_ work: StepInput = .empty) -> StepOutcome {
        lock.lock()

        // Locked state: reject without advancing.
        if _lifecycle == .locked {
            lock.unlock()
            emit(kind: "engine.step.rejected", data: [
                "reason": .string("locked"),
                "requested_tokens": .int(work.tokens),
                "requested_tools": .int(work.toolCalls),
            ])
            return .locked
        }

        let now = clock.now()
        let elapsed = max(0, now - _lastStepAt)
        let delta = (Double(work.tokens) / 1000.0) * config.tokenCoefficient
            + Double(work.toolCalls) * config.toolCoefficient
            + Double(work.depth) * config.depthCoefficient
        let decay = config.dissipationPerStep + elapsed * config.dissipationPerSecond

        _pressure = clamp01(_pressure + delta - decay)
        _stepCount += 1
        _lastStepAt = now
        _lifecycle = .running

        let stepData: [String: AnyJSON] = [
            "step": .int(_stepCount),
            "pressure": .double(_pressure),
            "delta": .double(delta),
            "decay": .double(decay),
            "tokens": .int(work.tokens),
            "tool_calls": .int(work.toolCalls),
            "depth": .int(work.depth),
            "tag": work.tag.map { .string($0) } ?? .null,
        ]
        let pressureNow = _pressure
        let releaseThr = config.releaseThreshold
        let escThr = config.escalationThreshold
        let postReleaseLock = config.postReleaseLock

        lock.unlock()
        emit(kind: "engine.step", data: stepData)

        if pressureNow >= releaseThr {
            emit(kind: "engine.release", data: [
                "pressure": .double(pressureNow),
                "threshold": .double(releaseThr),
            ])
            lock.lock()
            _pressure = 0
            if postReleaseLock {
                _lifecycle = .locked
                lock.unlock()
                emit(kind: "engine.locked", data: ["reason": .string("post_release_lock")])
            } else {
                _lifecycle = .running
                lock.unlock()
            }
            return .released
        }
        if pressureNow >= escThr {
            lock.lock()
            _lifecycle = .escalated
            lock.unlock()
            emit(kind: "engine.escalation", data: [
                "pressure": .double(pressureNow),
                "threshold": .double(escThr),
            ])
            return .escalated
        }
        return .ok
    }

    /// Reset the engine. Emits `engine.reset`.
    @discardableResult
    public func reset() -> PressureSnapshot {
        lock.lock()
        _pressure = 0
        _stepCount = 0
        _lastStepAt = clock.now()
        _lifecycle = .init
        let snap = PressureSnapshot(
            pressure: _pressure, step: _stepCount,
            lifecycle: _lifecycle, lastStepAt: _lastStepAt)
        lock.unlock()
        emit(kind: "engine.reset", data: ["pressure": .double(0)])
        return snap
    }

    private func emit(kind: String, data: [String: AnyJSON]) {
        audit.emit(Event(
            executionId: executionId,
            kind: kind,
            timestamp: timestampClock.now(),
            data: data))
    }

    private func clamp01(_ v: Double) -> Double {
        if v < 0 { return 0 }
        if v > 1 { return 1 }
        return v
    }
}
