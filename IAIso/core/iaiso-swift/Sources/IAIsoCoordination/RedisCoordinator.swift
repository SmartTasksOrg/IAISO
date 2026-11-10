import Foundation
import IAIsoAudit
import IAIsoCore
import IAIsoPolicy

/// Structural Redis client interface. Implement this around your favorite
/// Redis library (Vapor's Redis, RediStack, RedisKit, or any other) to
/// plug it into `RedisCoordinator`.
public protocol RedisClient {
    /// Run a Lua script. Returns the parsed reply (list, map, string, or int).
    func eval(_ script: String, keys: [String], args: [String]) throws -> Any?

    /// HSET key field value [field value ...]
    func hset(_ key: String, fieldValuePairs: [(String, String)]) throws

    /// HKEYS key
    func hkeys(_ key: String) throws -> [String]
}

/// Redis-backed coordinator. Interoperable with the Python, Node, Go, Rust,
/// Java, C#, and PHP references via the shared keyspace and the verbatim
/// Lua script in `RedisCoordinator.UPDATE_AND_FETCH_SCRIPT`.
public final class RedisCoordinator: @unchecked Sendable {

    /// The normative Lua script — verbatim from `spec/coordinator/README.md §1.2`.
    /// Bytes are identical across all reference SDKs to ensure cross-language
    /// fleet coordination.
    public static let UPDATE_AND_FETCH_SCRIPT: String =
        "\nlocal pressures_key = KEYS[1]\n"
        + "local exec_id       = ARGV[1]\n"
        + "local new_pressure  = ARGV[2]\n"
        + "local ttl_seconds   = tonumber(ARGV[3])\n"
        + "\n"
        + "redis.call('HSET', pressures_key, exec_id, new_pressure)\n"
        + "if ttl_seconds > 0 then\n"
        + "  redis.call('EXPIRE', pressures_key, ttl_seconds)\n"
        + "end\n"
        + "\n"
        + "return redis.call('HGETALL', pressures_key)\n"

    private let redis: RedisClient
    private let keyPrefix: String
    private let pressuresTTLSeconds: Int
    private let shadow: SharedPressureCoordinator
    private let auditSink: Sink
    private let clock: Clock

    public init(
        redis: RedisClient,
        coordinatorId: String = "default",
        escalationThreshold: Double = 5.0,
        releaseThreshold: Double = 8.0,
        notifyCooldownSeconds: Double = 1.0,
        keyPrefix: String = "iaiso:coord",
        pressuresTTLSeconds: Int = 300,
        aggregator: Aggregator = SumAggregator(),
        auditSink: Sink = NullSink.shared,
        onEscalation: (@Sendable (Snapshot) -> Void)? = nil,
        onRelease: (@Sendable (Snapshot) -> Void)? = nil,
        clock: Clock = WallClock.shared
    ) throws {
        self.redis = redis
        self.keyPrefix = keyPrefix
        self.pressuresTTLSeconds = pressuresTTLSeconds
        self.auditSink = auditSink
        self.clock = clock
        // Shadow coordinator runs the lifecycle/notify logic locally; suppress
        // its `coordinator.init` event so we can emit our own with backend=redis.
        self.shadow = try SharedPressureCoordinator(
            coordinatorId: coordinatorId,
            escalationThreshold: escalationThreshold,
            releaseThreshold: releaseThreshold,
            notifyCooldownSeconds: notifyCooldownSeconds,
            aggregator: aggregator,
            auditSink: NullSink.shared,
            onEscalation: onEscalation,
            onRelease: onRelease,
            clock: clock,
            emitInit: false)
        auditSink.emit(Event(
            executionId: "coord:\(coordinatorId)",
            kind: "coordinator.init",
            timestamp: clock.now(),
            data: [
                "coordinator_id": .string(coordinatorId),
                "aggregator": .string(aggregator.name),
                "backend": .string("redis"),
            ]))
    }

    private var pressuresKey: String {
        return "\(keyPrefix):\(shadow.coordinatorId):pressures"
    }

    @discardableResult
    public func register(_ executionId: String) throws -> Snapshot {
        try redis.hset(pressuresKey, fieldValuePairs: [(executionId, "0.0")])
        return shadow.register(executionId)
    }

    @discardableResult
    public func unregister(_ executionId: String) throws -> Snapshot {
        _ = try redis.eval(
            "redis.call('HDEL', KEYS[1], ARGV[1]); return 1",
            keys: [pressuresKey],
            args: [executionId])
        return shadow.unregister(executionId)
    }

    @discardableResult
    public func update(_ executionId: String, pressure: Double) throws -> Snapshot {
        guard pressure >= 0, pressure <= 1 else {
            throw CoordinatorError("pressure must be in [0, 1], got \(pressure)")
        }
        let reply = try redis.eval(
            RedisCoordinator.UPDATE_AND_FETCH_SCRIPT,
            keys: [pressuresKey],
            args: [executionId, "\(pressure)", "\(pressuresTTLSeconds)"])
        let updated = RedisCoordinator.parseHGetAllFlat(reply)
        shadow.setPressuresFromMap(updated)
        return shadow.evaluate()
    }

    @discardableResult
    public func reset() throws -> Int {
        let keys = try redis.hkeys(pressuresKey)
        if !keys.isEmpty {
            let pairs = keys.map { ($0, "0.0") }
            try redis.hset(pressuresKey, fieldValuePairs: pairs)
        }
        return shadow.reset()
    }

    public func snapshot() -> Snapshot { shadow.snapshot() }

    /// Parse an HGETALL Redis reply into a [String: Double] map.
    /// Accepts a flat list (k0, v0, k1, v1, …) or a [String: Any] map.
    public static func parseHGetAllFlat(_ reply: Any?) -> [String: Double] {
        var out: [String: Double] = [:]
        if let map = reply as? [String: Any] {
            for (k, v) in map {
                out[k] = (v as? Double) ?? Double((v as? String) ?? "0") ?? 0
            }
            return out
        }
        if let arr = reply as? [Any] {
            var i = 0
            while i + 1 < arr.count {
                let k = (arr[i] as? String) ?? String(describing: arr[i])
                let vRaw = arr[i + 1]
                let v = (vRaw as? Double) ?? Double((vRaw as? String) ?? "0") ?? 0
                out[k] = v
                i += 2
            }
        }
        return out
    }
}
