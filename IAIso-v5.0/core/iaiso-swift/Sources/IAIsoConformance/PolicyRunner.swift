import Foundation
import IAIsoPolicy

/// Runs the policy section of the conformance suite.
public enum PolicyRunner {
    public static let TOLERANCE: Double = 1e-9

    public static func run(specRoot: String) throws -> [VectorResult] {
        let path = "\(specRoot)/policy/vectors.json"
        let data = try Data(contentsOf: URL(fileURLWithPath: path))
        guard let doc = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return [VectorResult.fail("policy", "load", "could not parse vectors.json")]
        }
        var out: [VectorResult] = []
        for v in (doc["valid"] as? [[String: Any]] ?? []) {
            out.append(runValid(v))
        }
        for v in (doc["invalid"] as? [[String: Any]] ?? []) {
            out.append(runInvalid(v))
        }
        return out
    }

    private static func runValid(_ v: [String: Any]) -> VectorResult {
        let name = "valid/\((v["name"] as? String) ?? "?")"
        do {
            let p = try PolicyLoader.build(v["document"])
            if let ep = v["expected_pressure"] as? [String: Any] {
                if let err = checkPressure(p, ep) {
                    return VectorResult.fail("policy", name, err)
                }
            }
            if let ec = v["expected_consent"] as? [String: Any] {
                if let err = checkConsent(p, ec) {
                    return VectorResult.fail("policy", name, err)
                }
            }
            if let em = v["expected_metadata"] as? [String: Any] {
                if em.count != p.metadata.count {
                    return VectorResult.fail("policy", name,
                        "metadata size: got \(p.metadata.count), want \(em.count)")
                }
            }
            return VectorResult.pass("policy", name)
        } catch {
            return VectorResult.fail("policy", name, "build failed: \(error)")
        }
    }

    private static func checkPressure(_ p: Policy, _ ep: [String: Any]) -> String? {
        let pairs: [(String, Double)] = [
            ("token_coefficient", p.pressure.tokenCoefficient),
            ("tool_coefficient", p.pressure.toolCoefficient),
            ("depth_coefficient", p.pressure.depthCoefficient),
            ("dissipation_per_step", p.pressure.dissipationPerStep),
            ("dissipation_per_second", p.pressure.dissipationPerSecond),
            ("escalation_threshold", p.pressure.escalationThreshold),
            ("release_threshold", p.pressure.releaseThreshold),
        ]
        for (k, got) in pairs {
            if let want = num(ep[k]), abs(got - want) > TOLERANCE {
                return "\(k): got \(got), want \(want)"
            }
        }
        if let want = ep["post_release_lock"] as? Bool,
           want != p.pressure.postReleaseLock {
            return "post_release_lock mismatch"
        }
        return nil
    }

    private static func checkConsent(_ p: Policy, _ ec: [String: Any]) -> String? {
        if ec.keys.contains("issuer") {
            let want = ec["issuer"] as? String
            if want != p.consent.issuer {
                return "consent.issuer: got \(p.consent.issuer ?? "nil"), want \(want ?? "nil")"
            }
        }
        if let want = num(ec["default_ttl_seconds"]),
           abs(p.consent.defaultTTLSeconds - want) > TOLERANCE {
            return "default_ttl_seconds: got \(p.consent.defaultTTLSeconds), want \(want)"
        }
        if let want = ec["required_scopes"] as? [Any],
           want.count != p.consent.requiredScopes.count {
            return "required_scopes length mismatch"
        }
        if let want = ec["allowed_algorithms"] as? [Any],
           want.count != p.consent.allowedAlgorithms.count {
            return "allowed_algorithms length mismatch"
        }
        return nil
    }

    private static func runInvalid(_ v: [String: Any]) -> VectorResult {
        let name = "invalid/\((v["name"] as? String) ?? "?")"
        let expectPath = (v["expect_error_path"] as? String) ?? ""
        do {
            _ = try PolicyLoader.build(v["document"])
            return VectorResult.fail("policy", name,
                "expected error containing '\(expectPath)', got Ok")
        } catch let err as PolicyError {
            if err.message.contains(expectPath) {
                return VectorResult.pass("policy", name)
            }
            return VectorResult.fail("policy", name,
                "expected error containing '\(expectPath)', got: \(err.message)")
        } catch {
            return VectorResult.fail("policy", name, "unexpected error: \(error)")
        }
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
