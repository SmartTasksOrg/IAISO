import Foundation

/// Top-level conformance runner.
public enum ConformanceRunner {

    /// Run every section against the spec at `specRoot`.
    public static func runAll(specRoot: String) throws -> SectionResults {
        var r = SectionResults()
        r.pressure = try PressureRunner.run(specRoot: specRoot)
        r.consent  = try ConsentRunner.run(specRoot: specRoot)
        r.events   = try EventsRunner.run(specRoot: specRoot)
        r.policy   = try PolicyRunner.run(specRoot: specRoot)
        return r
    }
}
