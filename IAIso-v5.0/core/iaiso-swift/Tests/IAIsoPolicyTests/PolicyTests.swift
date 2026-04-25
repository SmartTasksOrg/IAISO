import XCTest
@testable import IAIsoPolicy

final class PolicyTests: XCTestCase {

    func testBuildMinimalPolicy() throws {
        let p = try PolicyLoader.build(["version": "1"])
        XCTAssertEqual(p.version, "1")
        XCTAssertEqual(p.aggregator.name, "sum")
    }

    func testBuildOverridesDefaults() throws {
        let p = try PolicyLoader.build([
            "version": "1",
            "pressure": ["escalation_threshold": 0.7, "release_threshold": 0.85],
            "coordinator": ["aggregator": "max"],
        ] as [String: Any])
        XCTAssertEqual(p.pressure.escalationThreshold, 0.7, accuracy: 1e-9)
        XCTAssertEqual(p.aggregator.name, "max")
    }

    func testRejectsMissingVersion() {
        XCTAssertThrowsError(try PolicyLoader.build(["metadata": ["x": "y"]] as [String: Any]))
    }

    func testRejectsBadVersion() {
        XCTAssertThrowsError(try PolicyLoader.build(["version": "2"]))
    }

    func testRejectsReleaseBelowEscalation() {
        XCTAssertThrowsError(try PolicyLoader.build([
            "version": "1",
            "pressure": ["escalation_threshold": 0.9, "release_threshold": 0.5],
        ] as [String: Any]))
    }

    func testRejectsStringAsNumber() {
        XCTAssertThrowsError(try PolicyLoader.build([
            "version": "1",
            "pressure": ["token_coefficient": "0.015"],
        ] as [String: Any]))
    }

    func testSumAggregator() {
        XCTAssertEqual(SumAggregator().aggregate(["a": 0.3, "b": 0.5]), 0.8, accuracy: 1e-9)
    }

    func testMaxAggregator() {
        XCTAssertEqual(MaxAggregator().aggregate(["a": 0.3, "b": 0.5]), 0.5, accuracy: 1e-9)
    }

    func testWeightedSumAggregator() {
        let a = WeightedSumAggregator(weights: ["important": 2.0], defaultWeight: 1.0)
        XCTAssertEqual(
            a.aggregate(["important": 0.5, "normal": 0.3]), 1.3, accuracy: 1e-9)
    }
}
