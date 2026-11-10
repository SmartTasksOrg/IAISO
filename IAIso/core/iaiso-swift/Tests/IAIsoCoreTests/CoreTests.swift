import XCTest
@testable import IAIsoAudit
@testable import IAIsoCore

final class CoreTests: XCTestCase {

    func testEnumWireValuesMatchSpec() {
        XCTAssertEqual(Lifecycle.`init`.rawValue, "init")
        XCTAssertEqual(Lifecycle.running.rawValue, "running")
        XCTAssertEqual(Lifecycle.escalated.rawValue, "escalated")
        XCTAssertEqual(Lifecycle.released.rawValue, "released")
        XCTAssertEqual(Lifecycle.locked.rawValue, "locked")
        XCTAssertEqual(StepOutcome.ok.rawValue, "ok")
    }

    func testConfigRejectsBadThresholds() {
        let cfg = PressureConfig(escalationThreshold: 0.9, releaseThreshold: 0.5)
        XCTAssertThrowsError(try cfg.validate())
    }

    func testConfigRejectsNegativeCoefficient() {
        let cfg = PressureConfig(tokenCoefficient: -1.0)
        XCTAssertThrowsError(try cfg.validate())
    }

    func testEngineEscalatesOnHighPressure() throws {
        let sink = MemorySink()
        let clk = ScriptedClock([0.0, 1.0])
        let cfg = PressureConfig(
            depthCoefficient: 0.6,
            dissipationPerStep: 0.0,
            escalationThreshold: 0.5,
            releaseThreshold: 0.95)
        let eng = try PressureEngine(
            config: cfg,
            options: EngineOptions(executionId: "e", auditSink: sink, clock: clk, timestampClock: clk))
        let outcome = eng.step(StepInput(depth: 1))
        XCTAssertEqual(outcome, .escalated)
        XCTAssertEqual(eng.pressure, 0.6, accuracy: 1e-9)
    }

    func testEngineLocksAfterRelease() throws {
        let clk = ScriptedClock([0.0, 1.0, 2.0])
        let cfg = PressureConfig(
            depthCoefficient: 1.0,
            dissipationPerStep: 0.0,
            escalationThreshold: 0.5,
            releaseThreshold: 0.9,
            postReleaseLock: true)
        let eng = try PressureEngine(
            config: cfg,
            options: EngineOptions(executionId: "e", clock: clk, timestampClock: clk))
        _ = eng.step(StepInput(depth: 1))
        XCTAssertEqual(eng.lifecycle, .locked)
        XCTAssertEqual(eng.step(StepInput(depth: 1)), .locked)
    }

    func testEngineResetEmitsResetEvent() throws {
        let sink = MemorySink()
        let clk = ScriptedClock([0.0, 1.0, 2.0])
        let eng = try PressureEngine(
            config: .defaults,
            options: EngineOptions(executionId: "e", auditSink: sink, clock: clk, timestampClock: clk))
        _ = eng.step(StepInput(tokens: 100))
        eng.reset()
        let kinds = sink.events.map { $0.kind }
        XCTAssertTrue(kinds.contains("engine.reset"))
        XCTAssertEqual(eng.pressure, 0.0)
        XCTAssertEqual(eng.lifecycle, .`init`)
    }

    func testBoundedExecutionRunEmitsClosed() throws {
        let sink = MemorySink()
        try BoundedExecution.run(
            BoundedExecution.Options(executionId: "e1", auditSink: sink),
            body: { ex in ex.recordTokens(100, tag: "x") })
        let kinds = sink.events.map { $0.kind }
        XCTAssertTrue(kinds.contains("execution.closed"))
    }

    func testRecordToolCallAdvancesEngine() throws {
        let exec = try BoundedExecution.start()
        XCTAssertEqual(exec.recordToolCall("search", tokens: 100), .ok)
        XCTAssertGreaterThan(exec.snapshot().pressure, 0)
        exec.close()
    }
}
