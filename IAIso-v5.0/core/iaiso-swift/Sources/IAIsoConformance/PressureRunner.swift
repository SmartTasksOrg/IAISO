import Foundation
import IAIsoAudit
import IAIsoCore

/// Runs the pressure section of the conformance suite.
public enum PressureRunner {
    public static let TOLERANCE: Double = 1e-9

    public static func run(specRoot: String) throws -> [VectorResult] {
        let path = "\(specRoot)/pressure/vectors.json"
        let data = try Data(contentsOf: URL(fileURLWithPath: path))
        guard let doc = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let vectors = doc["vectors"] as? [[String: Any]] else {
            return [VectorResult.fail("pressure", "load", "could not parse vectors.json")]
        }
        return vectors.map(runOne)
    }

    private static func runOne(_ v: [String: Any]) -> VectorResult {
        let name = (v["name"] as? String) ?? "?"
        var cfg = PressureConfig.defaults
        if let c = v["config"] as? [String: Any] {
            if let n = numericValue(c["escalation_threshold"]) { cfg.escalationThreshold = n }
            if let n = numericValue(c["release_threshold"]) { cfg.releaseThreshold = n }
            if let n = numericValue(c["dissipation_per_step"]) { cfg.dissipationPerStep = n }
            if let n = numericValue(c["dissipation_per_second"]) { cfg.dissipationPerSecond = n }
            if let n = numericValue(c["token_coefficient"]) { cfg.tokenCoefficient = n }
            if let n = numericValue(c["tool_coefficient"]) { cfg.toolCoefficient = n }
            if let n = numericValue(c["depth_coefficient"]) { cfg.depthCoefficient = n }
            if let b = c["post_release_lock"] as? Bool { cfg.postReleaseLock = b }
        }

        let clockSeq: [Double] = (v["clock"] as? [Any])?.compactMap { numericValue($0) } ?? [0.0]
        let clk = ScriptedClock(clockSeq)

        let expectErr = v["expect_config_error"] as? String
        let engine: PressureEngine
        do {
            engine = try PressureEngine(
                config: cfg,
                options: EngineOptions(executionId: "vec-\(name)",
                                       auditSink: NullSink.shared,
                                       clock: clk, timestampClock: clk))
        } catch let err as ConfigError {
            if let want = expectErr {
                if err.message.contains(want) {
                    return VectorResult.pass("pressure", name)
                }
                return VectorResult.fail("pressure", name,
                    "expected error containing '\(want)', got: \(err.message)")
            }
            return VectorResult.fail("pressure", name,
                "engine construction failed: \(err.message)")
        } catch {
            return VectorResult.fail("pressure", name, "unexpected error: \(error)")
        }
        if let want = expectErr {
            return VectorResult.fail("pressure", name,
                "expected config error containing '\(want)', got Ok")
        }

        if let init0 = v["expected_initial"] as? [String: Any] {
            let snap = engine.snapshot()
            if let p = numericValue(init0["pressure"]),
               abs(snap.pressure - p) > TOLERANCE {
                return VectorResult.fail("pressure", name,
                    "initial pressure: got \(snap.pressure), want \(p)")
            }
            if let s = init0["step"] as? Int, snap.step != Int64(s) {
                return VectorResult.fail("pressure", name,
                    "initial step: got \(snap.step), want \(s)")
            }
            if let l = init0["lifecycle"] as? String, snap.lifecycle.rawValue != l {
                return VectorResult.fail("pressure", name,
                    "initial lifecycle: got \(snap.lifecycle.rawValue), want \(l)")
            }
            if let ls = numericValue(init0["last_step_at"]),
               abs(snap.lastStepAt - ls) > TOLERANCE {
                return VectorResult.fail("pressure", name,
                    "initial last_step_at: got \(snap.lastStepAt), want \(ls)")
            }
        }

        let steps = (v["steps"] as? [[String: Any]]) ?? []
        let expSteps = (v["expected_steps"] as? [[String: Any]]) ?? []
        for (i, step) in steps.enumerated() {
            let outcome: StepOutcome
            if let r = step["reset"] as? Bool, r {
                engine.reset()
                outcome = .ok
            } else {
                var work = StepInput()
                if let n = step["tokens"] as? Int { work.tokens = Int64(n) }
                if let n = step["tool_calls"] as? Int { work.toolCalls = Int64(n) }
                if let n = step["depth"] as? Int { work.depth = Int64(n) }
                if let s = step["tag"] as? String { work.tag = s }
                outcome = engine.step(work)
            }
            guard i < expSteps.count else {
                return VectorResult.fail("pressure", name, "step \(i): no expected entry")
            }
            let exp = expSteps[i]
            if let want = exp["outcome"] as? String, outcome.rawValue != want {
                return VectorResult.fail("pressure", name,
                    "step \(i): outcome got \(outcome.rawValue), want \(want)")
            }
            let snap = engine.snapshot()
            if let p = numericValue(exp["pressure"]),
               abs(snap.pressure - p) > TOLERANCE {
                return VectorResult.fail("pressure", name,
                    "step \(i): pressure got \(snap.pressure), want \(p)")
            }
            if let s = exp["step"] as? Int, snap.step != Int64(s) {
                return VectorResult.fail("pressure", name,
                    "step \(i): step got \(snap.step), want \(s)")
            }
            if let l = exp["lifecycle"] as? String, snap.lifecycle.rawValue != l {
                return VectorResult.fail("pressure", name,
                    "step \(i): lifecycle got \(snap.lifecycle.rawValue), want \(l)")
            }
        }
        return VectorResult.pass("pressure", name)
    }

    static func numericValue(_ v: Any?) -> Double? {
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
