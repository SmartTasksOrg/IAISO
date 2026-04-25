import XCTest
@testable import IAIsoAudit

final class AuditTests: XCTestCase {

    func testEventEmitsFieldsInSpecOrder() {
        let e = Event(executionId: "exec-1", kind: "engine.init", timestamp: 0.0,
                      data: ["pressure": .double(0)])
        let json = e.toJSON()
        XCTAssertTrue(json.hasPrefix("{\"schema_version\":"))
        guard let svPos = json.range(of: "\"schema_version\"")?.lowerBound,
              let eiPos = json.range(of: "\"execution_id\"")?.lowerBound,
              let knPos = json.range(of: "\"kind\"")?.lowerBound,
              let tsPos = json.range(of: "\"timestamp\"")?.lowerBound,
              let dtPos = json.range(of: "\"data\"")?.lowerBound else {
            XCTFail("missing field"); return
        }
        XCTAssertLessThan(svPos, eiPos)
        XCTAssertLessThan(eiPos, knPos)
        XCTAssertLessThan(knPos, tsPos)
        XCTAssertLessThan(tsPos, dtPos)
    }

    func testIntegerFloatsSerializeAsIntegers() {
        let e = Event(executionId: "e", kind: "k", timestamp: 0.0,
                      data: ["n": .double(0)])
        let json = e.toJSON()
        XCTAssertTrue(json.contains("\"timestamp\":0"))
        XCTAssertFalse(json.contains("\"timestamp\":0.0"))
        XCTAssertTrue(json.contains("\"n\":0"))
    }

    func testDataKeysSortedAlphabetically() {
        let e = Event(executionId: "e", kind: "k", timestamp: 0.0,
                      data: ["z": .int(1), "a": .int(2), "m": .int(3)])
        let json = e.toJSON()
        let aPos = json.range(of: "\"a\"")!.lowerBound
        let mPos = json.range(of: "\"m\"")!.lowerBound
        let zPos = json.range(of: "\"z\"")!.lowerBound
        XCTAssertLessThan(aPos, mPos)
        XCTAssertLessThan(mPos, zPos)
    }

    func testNullDataValuesEmit() {
        let e = Event(executionId: "e", kind: "k", timestamp: 0.0,
                      data: ["tag": .null])
        XCTAssertTrue(e.toJSON().contains("\"tag\":null"))
    }

    func testMemorySinkStoresEvents() {
        let sink = MemorySink()
        sink.emit(Event(executionId: "e", kind: "a", timestamp: 0, data: [:]))
        sink.emit(Event(executionId: "e", kind: "b", timestamp: 0, data: [:]))
        XCTAssertEqual(sink.events.count, 2)
        XCTAssertEqual(sink.events[0].kind, "a")
    }

    func testFanoutSinkBroadcasts() {
        let a = MemorySink()
        let b = MemorySink()
        let f = FanoutSink([a, b])
        f.emit(Event(executionId: "e", kind: "k", timestamp: 0, data: [:]))
        XCTAssertEqual(a.events.count, 1)
        XCTAssertEqual(b.events.count, 1)
    }

    func testJsonlFileSinkAppends() throws {
        let url = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("iaiso-audit-\(UUID().uuidString).jsonl")
        defer { try? FileManager.default.removeItem(at: url) }
        let sink = JSONLFileSink(url: url)
        sink.emit(Event(executionId: "e", kind: "a", timestamp: 0, data: [:]))
        sink.emit(Event(executionId: "e", kind: "b", timestamp: 0, data: [:]))
        let contents = try String(contentsOf: url)
        let lines = contents.split(separator: "\n").filter { !$0.isEmpty }
        XCTAssertEqual(lines.count, 2)
        for line in lines {
            let data = line.data(using: .utf8)!
            let obj = try JSONSerialization.jsonObject(with: data) as? [String: Any]
            XCTAssertNotNil(obj?["schema_version"])
        }
    }

    func testNullSinkSwallowsEvents() {
        NullSink.shared.emit(Event(executionId: "e", kind: "k", timestamp: 0, data: [:]))
        XCTAssertTrue(true)
    }

    func testEncodeNumberHandlesIntFloats() {
        XCTAssertEqual(JSONEncoding.encodeNumber(0.0), "0")
        XCTAssertEqual(JSONEncoding.encodeNumber(1.0), "1")
        XCTAssertEqual(JSONEncoding.encodeNumber(0.5), "0.5")
    }
}
