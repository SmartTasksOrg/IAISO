import Foundation
import IAIsoAudit
import IAIsoCore
import IAIsoPolicy

/// In-memory coordinator that aggregates pressure across a single
/// process's executions.
public class SharedPressureCoordinator: @unchecked Sendable {

    public let coordinatorId: String
    public let escalationThreshold: Double
    public let releaseThreshold: Double
    public let notifyCooldownSeconds: Double
    public let aggregator: Aggregator

    private let auditSink: Sink
    private let clock: Clock
    private let onEscalation: (@Sendable (Snapshot) -> Void)?
    private let onRelease: (@Sendable (Snapshot) -> Void)?

    private let lock = NSLock()
    private var pressures: [String: Double] = [:]
    private var lifecycle: CoordinatorLifecycle = .nominal
    private var lastNotifyAt: Double = 0

    public init(
        coordinatorId: String = "default",
        escalationThreshold: Double = 5.0,
        releaseThreshold: Double = 8.0,
        notifyCooldownSeconds: Double = 1.0,
        aggregator: Aggregator = SumAggregator(),
        auditSink: Sink = NullSink.shared,
        onEscalation: (@Sendable (Snapshot) -> Void)? = nil,
        onRelease: (@Sendable (Snapshot) -> Void)? = nil,
        clock: Clock = WallClock.shared,
        emitInit: Bool = true
    ) throws {
        guard releaseThreshold > escalationThreshold else {
            throw CoordinatorError(
                "release_threshold must exceed escalation_threshold (\(releaseThreshold) <= \(escalationThreshold))")
        }
        self.coordinatorId = coordinatorId
        self.escalationThreshold = escalationThreshold
        self.releaseThreshold = releaseThreshold
        self.notifyCooldownSeconds = notifyCooldownSeconds
        self.aggregator = aggregator
        self.auditSink = auditSink
        self.onEscalation = onEscalation
        self.onRelease = onRelease
        self.clock = clock

        if emitInit {
            emit("coordinator.init", data: [
                "coordinator_id": .string(coordinatorId),
                "aggregator": .string(aggregator.name),
                "backend": .string("memory"),
            ])
        }
    }

    @discardableResult
    public func register(_ executionId: String) -> Snapshot {
        lock.lock()
        pressures[executionId] = 0.0
        lock.unlock()
        emit("coordinator.execution_registered", data: [
            "execution_id": .string(executionId),
        ])
        return snapshot()
    }

    @discardableResult
    public func unregister(_ executionId: String) -> Snapshot {
        lock.lock()
        pressures.removeValue(forKey: executionId)
        lock.unlock()
        emit("coordinator.execution_unregistered", data: [
            "execution_id": .string(executionId),
        ])
        return snapshot()
    }

    @discardableResult
    public func update(_ executionId: String, pressure: Double) throws -> Snapshot {
        guard pressure >= 0, pressure <= 1 else {
            throw CoordinatorError("pressure must be in [0, 1], got \(pressure)")
        }
        lock.lock()
        pressures[executionId] = pressure
        lock.unlock()
        return evaluate()
    }

    @discardableResult
    public func reset() -> Int {
        lock.lock()
        let count = pressures.count
        for k in pressures.keys {
            pressures[k] = 0
        }
        lifecycle = .nominal
        lock.unlock()
        emit("coordinator.reset", data: ["fleet_size": .int(Int64(count))])
        return count
    }

    public func snapshot() -> Snapshot {
        lock.lock()
        defer { lock.unlock() }
        let agg = aggregator.aggregate(pressures)
        return Snapshot(
            coordinatorId: coordinatorId,
            aggregatePressure: agg,
            lifecycle: lifecycle,
            activeExecutions: pressures.count,
            perExecution: pressures)
    }

    /// Replace per-execution pressures wholesale. Used by the Redis variant.
    func setPressuresFromMap(_ updated: [String: Double]) {
        lock.lock()
        pressures = updated
        lock.unlock()
    }

    @discardableResult
    func evaluate() -> Snapshot {
        let now = clock.now()
        lock.lock()
        let agg = aggregator.aggregate(pressures)
        let prior = lifecycle
        let inCooldown = (now - lastNotifyAt) < notifyCooldownSeconds

        let next: CoordinatorLifecycle
        if agg >= releaseThreshold {
            next = .released
        } else if agg >= escalationThreshold {
            next = (prior == .nominal) ? .escalated : prior
        } else {
            next = .nominal
        }
        lifecycle = next
        let pressuresCopy = pressures
        let activeCount = pressures.count

        var fireEsc = false
        var fireRel = false

        if next != prior, !inCooldown {
            lastNotifyAt = now
            switch next {
            case .released: fireRel = true
            case .escalated: fireEsc = true
            case .nominal: break
            }
        }
        lock.unlock()

        let snap = Snapshot(
            coordinatorId: coordinatorId,
            aggregatePressure: agg,
            lifecycle: next,
            activeExecutions: activeCount,
            perExecution: pressuresCopy)

        if fireRel {
            emit("coordinator.release", data: [
                "aggregate_pressure": .double(agg),
                "threshold": .double(releaseThreshold),
            ])
            onRelease?(snap)
        } else if fireEsc {
            emit("coordinator.escalation", data: [
                "aggregate_pressure": .double(agg),
                "threshold": .double(escalationThreshold),
            ])
            onEscalation?(snap)
        } else if next != prior, next == .nominal, !inCooldown {
            emit("coordinator.returned_to_nominal", data: [
                "aggregate_pressure": .double(agg),
            ])
        }
        return snap
    }

    private func emit(_ kind: String, data: [String: AnyJSON]) {
        auditSink.emit(Event(
            executionId: "coord:\(coordinatorId)",
            kind: kind,
            timestamp: clock.now(),
            data: data))
    }
}
