import Foundation
import IAIsoAudit
import IAIsoCore

/// Runs the events section of the conformance suite.
public enum EventsRunner {
    public static let TOLERANCE: Double = 1e-9

    public static func run(specRoot: String) throws -> [VectorResult] {
        let path = "\(specRoot)/events/vectors.json"
        let data = try Data(contentsOf: URL(fileURLWithPath: path))
        guard let doc = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let vectors = doc["vectors"] as? [[String: Any]] else {
            return [VectorResult.fail("events", "load", "could not parse vectors.json")]
        }
        return vectors.map(runOne)
    }

    private static func runOne(_ v: [String: Any]) -> VectorResult {
        let name = (v["name"] as? String) ?? "?"
        var cfg = PressureConfig.defaults
        if let c = v["config"] as? [String: Any] {
            if let n = num(c["escalation_threshold"]) { cfg.escalationThreshold = n }
            if let n = num(c["release_threshold"]) { cfg.releaseThreshold = n }
            if let n = num(c["dissipation_per_step"]) { cfg.dissipationPerStep = n }
            if let n = num(c["dissipation_per_second"]) { cfg.dissipationPerSecond = n }
            if let n = num(c["token_coefficient"]) { cfg.tokenCoefficient = n }
            if let n = num(c["tool_coefficient"]) { cfg.toolCoefficient = n }
            if let n = num(c["depth_coefficient"]) { cfg.depthCoefficient = n }
            if let b = c["post_release_lock"] as? Bool { cfg.postReleaseLock = b }
        }
        let clockSeq: [Double] = (v["clock"] as? [Any])?.compactMap { num($0) } ?? [0.0]
        let clk = ScriptedClock(clockSeq)

        let sink = MemorySink()
        let execId = (v["execution_id"] as? String) ?? "?"
        let engine: PressureEngine
        do {
            engine = try PressureEngine(
                config: cfg,
                options: EngineOptions(executionId: execId,
                                       auditSink: sink, clock: clk, timestampClock: clk))
        } catch {
            return VectorResult.fail("events", name, "engine init failed: \(error)")
        }

        let resetAfterStep = v["reset_after_step"] as? Int
        let steps = (v["steps"] as? [[String: Any]]) ?? []
        for (i, step) in steps.enumerated() {
            if let r = step["reset"] as? Bool, r {
                engine.reset()
            } else {
                var work = StepInput()
                if let n = step["tokens"] as? Int { work.tokens = Int64(n) }
                if let n = step["tool_calls"] as? Int { work.toolCalls = Int64(n) }
                if let n = step["depth"] as? Int { work.depth = Int64(n) }
                if let s = step["tag"] as? String { work.tag = s }
                engine.step(work)
            }
            if let after = resetAfterStep, (i + 1) == after {
                engine.reset()
            }
        }

        let got = sink.events
        guard let expected = v["expected_events"] as? [[String: Any]] else {
            return VectorResult.fail("events", name, "missing expected_events")
        }
        if got.count != expected.count {
            return VectorResult.fail("events", name,
                "event count: got \(got.count), want \(expected.count)")
        }
        for (i, exp) in expected.enumerated() {
            let actual = got[i]
            if let v = exp["schema_version"] as? String, !v.isEmpty,
               actual.schemaVersion != v {
                return VectorResult.fail("events", name,
                    "event \(i) schema_version: got \(actual.schemaVersion), want \(v)")
            }
            if let v = exp["execution_id"] as? String, !v.isEmpty,
               actual.executionId != v {
                return VectorResult.fail("events", name,
                    "event \(i) execution_id: got \(actual.executionId), want \(v)")
            }
            if let k = exp["kind"] as? String, actual.kind != k {
                return VectorResult.fail("events", name,
                    "event \(i) kind: got \(actual.kind), want \(k)")
            }
            if let dataExp = exp["data"] as? [String: Any] {
                if !dataMatches(actual: actual.data, want: dataExp) {
                    return VectorResult.fail("events", name,
                        "event \(i) data mismatch")
                }
            }
        }
        return VectorResult.pass("events", name)
    }

    private static func dataMatches(actual: [String: AnyJSON], want: [String: Any]) -> Bool {
        for (k, w) in want {
            let got = actual[k]
            if !valueEqual(got: got, want: w) { return false }
        }
        return true
    }

    private static func valueEqual(got: AnyJSON?, want: Any) -> Bool {
        if want is NSNull {
            if got == nil { return true }
            if case .null = got! { return true }
            return false
        }
        guard let got = got else { return false }
        // Distinguish Bool from numeric on Apple platforms where
        // JSONSerialization returns NSNumber for both. Without this check,
        // `1` (NSNumber) would match `Bool` first and incorrectly equal `true`.
        if let n = want as? NSNumber {
            #if canImport(ObjectiveC)
            if String(cString: n.objCType) == "c" {
                if case .bool(let g) = got { return g == n.boolValue }
                return false
            }
            #else
            // On Linux Foundation, Bool is its own type, not bridged.
            if let b = want as? Bool, type(of: want) == Bool.self {
                if case .bool(let g) = got { return g == b }
                return false
            }
            #endif
            // Numeric NSNumber.
            let nd = n.doubleValue
            if case .int(let i) = got { return abs(Double(i) - nd) <= TOLERANCE }
            if case .double(let d) = got { return abs(d - nd) <= TOLERANCE }
            return false
        }
        if let b = want as? Bool {
            if case .bool(let g) = got { return g == b }
            return false
        }
        if let n = num(want) {
            if case .int(let i) = got { return abs(Double(i) - n) <= TOLERANCE }
            if case .double(let d) = got { return abs(d - n) <= TOLERANCE }
            return false
        }
        if let s = want as? String {
            if case .string(let g) = got { return g == s }
            return false
        }
        if let arr = want as? [Any] {
            guard case .array(let g) = got, g.count == arr.count else { return false }
            for (i, w) in arr.enumerated() {
                if !valueEqual(got: g[i], want: w) { return false }
            }
            return true
        }
        if let m = want as? [String: Any] {
            guard case .object(let g) = got else { return false }
            for (k, w) in m {
                if !valueEqual(got: g[k], want: w) { return false }
            }
            return true
        }
        return false
    }

    private static func num(_ v: Any?) -> Double? {
        if let n = v as? NSNumber {
            #if canImport(ObjectiveC)
            if String(cString: n.objCType) == "c" { return nil }
            #endif
            return n.doubleValue
        }
        if let d = v as? Double { return d }
        if let i = v as? Int { return Double(i) }
        if let i = v as? Int64 { return Double(i) }
        return nil
    }
}
