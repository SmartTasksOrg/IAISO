import Foundation
import IAIsoCore

/// IAIso policy loader. JSON-only — to keep the SDK dependency-light.
/// Convert YAML policies to JSON outside this SDK if needed.
public enum PolicyLoader {

    private static let scopePattern = "^[a-z0-9_-]+(\\.[a-z0-9_-]+)*$"

    /// Validate a parsed JSON document against `spec/policy/README.md`.
    public static func validate(_ doc: Any?) throws {
        guard let map = doc as? [String: Any] else {
            throw PolicyError("$: policy document must be a mapping")
        }
        guard let v = map["version"] else {
            throw PolicyError("$: required property 'version' missing")
        }
        guard let vs = v as? String, vs == "1" else {
            throw PolicyError("$.version: must be exactly \"1\", got \(repr(v))")
        }

        if let p = map["pressure"] {
            guard let pmap = p as? [String: Any] else {
                throw PolicyError("$.pressure: must be a mapping")
            }
            let nonNeg = ["token_coefficient", "tool_coefficient", "depth_coefficient",
                          "dissipation_per_step", "dissipation_per_second"]
            for f in nonNeg {
                if let val = pmap[f] {
                    guard let n = numericValue(val) else {
                        throw PolicyError("$.pressure.\(f): expected number")
                    }
                    if n < 0 {
                        throw PolicyError("$.pressure.\(f): must be non-negative (got \(n))")
                    }
                }
            }
            for f in ["escalation_threshold", "release_threshold"] {
                if let val = pmap[f] {
                    guard let n = numericValue(val) else {
                        throw PolicyError("$.pressure.\(f): expected number")
                    }
                    if n < 0 || n > 1 {
                        throw PolicyError("$.pressure.\(f): must be in [0, 1] (got \(n))")
                    }
                }
            }
            if let prl = pmap["post_release_lock"] {
                guard isBool(prl) else {
                    throw PolicyError("$.pressure.post_release_lock: expected boolean")
                }
            }
            if let esc = numericValue(pmap["escalation_threshold"]),
               let rel = numericValue(pmap["release_threshold"]),
               rel <= esc {
                throw PolicyError(
                    "$.pressure.release_threshold: must exceed escalation_threshold (\(rel) <= \(esc))")
            }
        }

        if let c = map["coordinator"] {
            guard let cmap = c as? [String: Any] else {
                throw PolicyError("$.coordinator: must be a mapping")
            }
            if let agg = cmap["aggregator"] {
                guard let s = agg as? String,
                      ["sum", "mean", "max", "weighted_sum"].contains(s) else {
                    throw PolicyError(
                        "$.coordinator.aggregator: must be one of sum|mean|max|weighted_sum (got \(repr(agg)))")
                }
            }
            if let esc = numericValue(cmap["escalation_threshold"]),
               let rel = numericValue(cmap["release_threshold"]),
               rel <= esc {
                throw PolicyError(
                    "$.coordinator.release_threshold: must exceed escalation_threshold (\(rel) <= \(esc))")
            }
        }

        if let cn = map["consent"] {
            guard let cnmap = cn as? [String: Any] else {
                throw PolicyError("$.consent: must be a mapping")
            }
            if let scopes = cnmap["required_scopes"] {
                guard let arr = scopes as? [Any] else {
                    throw PolicyError("$.consent.required_scopes: expected list")
                }
                for (i, s) in arr.enumerated() {
                    guard let str = s as? String,
                          str.range(of: scopePattern, options: .regularExpression) != nil else {
                        throw PolicyError(
                            "$.consent.required_scopes[\(i)]: \(repr(s)) is not a valid scope")
                    }
                }
            }
        }
    }

    /// Build a `Policy` from a parsed JSON document.
    public static func build(_ doc: Any?) throws -> Policy {
        try validate(doc)
        guard let map = doc as? [String: Any] else {
            throw PolicyError("$: policy document must be a mapping")
        }

        var pressure = PressureConfig.defaults
        if let p = map["pressure"] as? [String: Any] {
            if let v = numericValue(p["escalation_threshold"]) { pressure.escalationThreshold = v }
            if let v = numericValue(p["release_threshold"]) { pressure.releaseThreshold = v }
            if let v = numericValue(p["dissipation_per_step"]) { pressure.dissipationPerStep = v }
            if let v = numericValue(p["dissipation_per_second"]) { pressure.dissipationPerSecond = v }
            if let v = numericValue(p["token_coefficient"]) { pressure.tokenCoefficient = v }
            if let v = numericValue(p["tool_coefficient"]) { pressure.toolCoefficient = v }
            if let v = numericValue(p["depth_coefficient"]) { pressure.depthCoefficient = v }
            if let prl = p["post_release_lock"] as? Bool { pressure.postReleaseLock = prl }
        }
        do {
            try pressure.validate()
        } catch let err as ConfigError {
            throw PolicyError("$.pressure: \(err.message)")
        }

        var coord = CoordinatorConfig.defaults
        var aggregator: Aggregator = SumAggregator()
        if let c = map["coordinator"] as? [String: Any] {
            if let v = numericValue(c["escalation_threshold"]) { coord.escalationThreshold = v }
            if let v = numericValue(c["release_threshold"]) { coord.releaseThreshold = v }
            if let v = numericValue(c["notify_cooldown_seconds"]) { coord.notifyCooldownSeconds = v }
            aggregator = buildAggregator(c)
        }

        var consent = ConsentPolicy.defaults
        if let cn = map["consent"] as? [String: Any] {
            if let s = cn["issuer"] as? String { consent.issuer = s }
            if let v = numericValue(cn["default_ttl_seconds"]) { consent.defaultTTLSeconds = v }
            if let scopes = cn["required_scopes"] as? [String] { consent.requiredScopes = scopes }
            if let algos = cn["allowed_algorithms"] as? [String] { consent.allowedAlgorithms = algos }
        }

        let metadata = (map["metadata"] as? [String: Any]) ?? [:]
        return Policy(version: "1",
                      pressure: pressure,
                      coordinator: coord,
                      consent: consent,
                      aggregator: aggregator,
                      metadata: metadata)
    }

    /// Parse JSON-encoded policy bytes.
    public static func parseJSON(_ data: Data) throws -> Policy {
        let doc = try JSONSerialization.jsonObject(with: data, options: [.fragmentsAllowed])
        return try build(doc)
    }

    /// Load a policy from a file. Only `.json` is supported.
    public static func load(_ path: String) throws -> Policy {
        guard path.lowercased().hasSuffix(".json") else {
            throw PolicyError(
                "unsupported policy file extension: \(path) (only .json is supported in the Swift SDK)")
        }
        let url = URL(fileURLWithPath: path)
        let data = try Data(contentsOf: url)
        return try parseJSON(data)
    }

    // MARK: - Internals

    private static func buildAggregator(_ c: [String: Any]) -> Aggregator {
        let name = (c["aggregator"] as? String) ?? "sum"
        switch name {
        case "mean": return MeanAggregator()
        case "max": return MaxAggregator()
        case "weighted_sum":
            var weights: [String: Double] = [:]
            if let w = c["weights"] as? [String: Any] {
                for (k, v) in w {
                    if let n = numericValue(v) { weights[k] = n }
                }
            }
            let dw = numericValue(c["default_weight"]) ?? 1.0
            return WeightedSumAggregator(weights: weights, defaultWeight: dw)
        default: return SumAggregator()
        }
    }

    /// Strict numeric extractor. Returns `nil` for strings that happen to
    /// parse as numbers (which is the gotcha we caught in the Java port).
    /// Returns `nil` for `Bool` even though Swift bridges Bool through
    /// `NSNumber` on Apple platforms.
    private static func numericValue(_ v: Any?) -> Double? {
        guard let v = v else { return nil }
        if v is String { return nil }
        if v is Bool { return nil }
        // On Apple platforms NSNumber wraps Bool; CFNumberGetType identifies it as charType.
        #if canImport(ObjectiveC)
        if let n = v as? NSNumber {
            let t = String(cString: n.objCType)
            if t == "c" { return nil } // Bool
            return n.doubleValue
        }
        #endif
        if let d = v as? Double { return d }
        if let i = v as? Int { return Double(i) }
        if let i = v as? Int64 { return Double(i) }
        if let f = v as? Float { return Double(f) }
        return nil
    }

    private static func isBool(_ v: Any?) -> Bool {
        if v is Bool { return true }
        #if canImport(ObjectiveC)
        if let n = v as? NSNumber, String(cString: n.objCType) == "c" { return true }
        #endif
        return false
    }

    private static func repr(_ v: Any?) -> String {
        guard let v = v else { return "null" }
        if let data = try? JSONSerialization.data(
            withJSONObject: [v], options: [.fragmentsAllowed]),
           let s = String(data: data, encoding: .utf8) {
            // Strip surrounding [ ]
            if s.hasPrefix("["), s.hasSuffix("]") {
                return String(s.dropFirst().dropLast())
            }
            return s
        }
        return String(describing: v)
    }
}
