import XCTest
@testable import IAIsoConformance

final class ConformanceSuiteTests: XCTestCase {

    /// Resolve the spec/ directory. Tries (in order): IAISO_SPEC_DIR env
    /// var, the package root relative to this file (../../../spec), and
    /// the current working directory's ./spec.
    private func resolveSpecRoot() -> String? {
        if let env = ProcessInfo.processInfo.environment["IAISO_SPEC_DIR"],
           !env.isEmpty {
            return env
        }
        // #file points at this test file. Package root is 3 levels up
        // from Tests/IAIsoConformanceTests/ConformanceSuiteTests.swift.
        let here = URL(fileURLWithPath: #file)
            .deletingLastPathComponent()  // IAIsoConformanceTests
            .deletingLastPathComponent()  // Tests
            .deletingLastPathComponent()  // package root
        let candidate = here.appendingPathComponent("spec")
        if FileManager.default.fileExists(atPath: candidate.path) {
            return candidate.path
        }
        let cwd = FileManager.default.currentDirectoryPath + "/spec"
        if FileManager.default.fileExists(atPath: cwd) {
            return cwd
        }
        return nil
    }

    func testAllVectorsPass() throws {
        guard let specRoot = resolveSpecRoot() else {
            throw XCTSkip(
                "spec dir not found; set IAISO_SPEC_DIR or run `swift test` from package root")
        }
        let r = try ConformanceRunner.runAll(specRoot: specRoot)
        var failures = ""
        for bucket in [r.pressure, r.consent, r.events, r.policy] {
            for v in bucket where !v.passed {
                failures += "\n  [\(v.section)] \(v.name): \(v.message)"
            }
        }
        XCTAssertEqual(r.countTotal(), 67, "expected 67 total vectors")
        XCTAssertEqual(r.countTotal() - r.countPassed(), 0,
                       "conformance \(r.countPassed())/\(r.countTotal()) — failures:\(failures)")
    }
}
