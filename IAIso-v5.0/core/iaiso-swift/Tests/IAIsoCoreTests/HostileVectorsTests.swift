import Foundation
import XCTest
import IAIsoAudit
@testable import IAIsoCore

/// spec/pressure/hostile.json is shared by every IAIso port.
/// NOTE: written without a Swift toolchain available; not compiled in the review run.
final class HostileVectorsTests: XCTestCase {
    private func hostile() throws -> [String: Any] {
        let here = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        let url = here.appendingPathComponent("spec/pressure/hostile.json")
        return try JSONSerialization.jsonObject(with: Data(contentsOf: url)) as! [String: Any]
    }

    private func engine() throws -> PressureEngine {
        let clk = ScriptedClock([0.0])
        return try PressureEngine(config: .defaults,
                                  options: EngineOptions(executionId: "hostile", auditSink: MemorySink(),
                                                         clock: clk, timestampClock: clk))
    }

    func testHostileValuesAreRefused() throws {
        let rejects = try hostile()["reject"] as! [[String: Any]]
        XCTAssertGreaterThanOrEqual(rejects.count, 18)
        for v in rejects {
            let field = v["field"] as! String
            let value = try JSONSerialization.data(withJSONObject: [v["value"]!], options: [.fragmentsAllowed])
            // value is "[x]"; strip the brackets to splice it in as a field value
            let raw = String(data: value, encoding: .utf8)!.dropFirst().dropLast()
            let json = Data("{\"\(field)\":\(raw)}".utf8)
            XCTAssertThrowsError(try StepInput.fromJSON(json), "\(v["name"]!) accepted")
        }
    }

    func testExtremeValuesAreHandled() throws {
        for v in try hostile()["accept"] as! [[String: Any]] {
            let step = try JSONSerialization.data(withJSONObject: v["step"]!)
            let e = try engine()
            let out = e.step(try StepInput.fromJSON(step))
            let exp = v["expect"] as! [String: Any]
            XCTAssertFalse(e.pressure.isNaN)
            XCTAssertEqual(e.pressure, (exp["pressure"] as! NSNumber).doubleValue, accuracy: 1e-9)
            XCTAssertEqual(out.rawValue, exp["outcome"] as? String)
            XCTAssertEqual(e.lifecycle.rawValue, exp["lifecycle"] as? String)
        }
    }
}
