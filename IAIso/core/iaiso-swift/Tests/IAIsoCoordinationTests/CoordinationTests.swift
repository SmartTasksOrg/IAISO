import XCTest
@testable import IAIsoAudit
@testable import IAIsoCoordination
@testable import IAIsoPolicy

final class CoordinationTests: XCTestCase {

    func testAggregatesSum() throws {
        let c = try SharedPressureCoordinator(auditSink: MemorySink())
        c.register("a")
        c.register("b")
        _ = try c.update("a", pressure: 0.3)
        let snap = try c.update("b", pressure: 0.5)
        XCTAssertEqual(snap.aggregatePressure, 0.8, accuracy: 1e-9)
    }

    func testEscalationCallbackFires() throws {
        var calls = 0
        let c = try SharedPressureCoordinator(
            escalationThreshold: 0.7, releaseThreshold: 0.95,
            notifyCooldownSeconds: 0.0,
            onEscalation: { _ in calls += 1 })
        c.register("a")
        _ = try c.update("a", pressure: 0.8)
        XCTAssertEqual(calls, 1)
    }

    func testRejectsBadPressure() throws {
        let c = try SharedPressureCoordinator()
        XCTAssertThrowsError(try c.update("a", pressure: 1.5))
    }

    func testLuaScriptUnchangedFromSpec() {
        let s = RedisCoordinator.UPDATE_AND_FETCH_SCRIPT
        XCTAssertTrue(s.contains("pressures_key = KEYS[1]"))
        XCTAssertTrue(s.contains("HGETALL"))
        XCTAssertTrue(s.contains("EXPIRE"))
    }

    func testParseHGetAllFlatWorks() {
        let reply: [Any] = ["a", "0.3", "b", "0.5"]
        let out = RedisCoordinator.parseHGetAllFlat(reply)
        XCTAssertEqual(out["a"]!, 0.3, accuracy: 1e-9)
        XCTAssertEqual(out["b"]!, 0.5, accuracy: 1e-9)
    }
}
