import Foundation
import IAIsoAudit
import IAIsoConformance
import IAIsoConsent
import IAIsoCoordination
import IAIsoCore
import IAIsoPolicy

let args = Array(CommandLine.arguments.dropFirst())

func printHelp() {
    print("""
    IAIso admin CLI

    Subcommands:
      policy validate <file>                 check a policy JSON file for errors
      policy template <file>                 write a blank policy template
      consent issue <sub> <scope,...> [ttl]  issue a token (needs IAISO_HS256_SECRET)
      consent verify <token>                 verify a token
      audit tail <jsonl-file>                pretty-print JSONL audit events
      audit stats <jsonl-file>               summarize events by kind
      coordinator demo                       in-memory coordinator smoke test
      conformance <spec-dir>                 run the conformance suite
    """)
}

func cmdPolicy(_ rest: [String]) -> Int32 {
    guard !rest.isEmpty else {
        FileHandle.standardError.write("usage: iaiso policy [validate|template] <file>\n".data(using: .utf8)!)
        return 2
    }
    let sub = rest[0]
    if sub == "validate" {
        guard rest.count == 2 else { return 2 }
        do {
            let p = try PolicyLoader.load(rest[1])
            print("OK: policy v\(p.version)")
            print("  pressure.escalation_threshold = \(p.pressure.escalationThreshold)")
            print("  coordinator.aggregator        = \(p.aggregator.name)")
            print("  consent.issuer                = \(p.consent.issuer ?? "(none)")")
            return 0
        } catch {
            FileHandle.standardError.write("INVALID: \(error)\n".data(using: .utf8)!)
            return 1
        }
    }
    if sub == "template" {
        guard rest.count == 2 else { return 2 }
        let body = """
        {
          "version": "1",
          "pressure": {
            "escalation_threshold": 0.85,
            "release_threshold": 0.95,
            "token_coefficient": 0.015,
            "tool_coefficient": 0.08,
            "depth_coefficient": 0.05,
            "dissipation_per_step": 0.02,
            "dissipation_per_second": 0.0,
            "post_release_lock": true
          },
          "coordinator": {
            "aggregator": "sum",
            "escalation_threshold": 5.0,
            "release_threshold": 8.0,
            "notify_cooldown_seconds": 1.0
          },
          "consent": {
            "issuer": "iaiso",
            "default_ttl_seconds": 3600,
            "required_scopes": [],
            "allowed_algorithms": ["HS256", "RS256"]
          },
          "metadata": {}
        }

        """
        do {
            try body.write(toFile: rest[1], atomically: true, encoding: .utf8)
            print("Wrote template to \(rest[1])")
            return 0
        } catch {
            FileHandle.standardError.write("write failed: \(error)\n".data(using: .utf8)!)
            return 1
        }
    }
    return 2
}

func cmdConsent(_ rest: [String]) -> Int32 {
    guard !rest.isEmpty else { return 2 }
    let env = ProcessInfo.processInfo.environment
    guard let secret = env["IAISO_HS256_SECRET"], !secret.isEmpty,
          let secretData = secret.data(using: .utf8) else {
        FileHandle.standardError.write("error: IAISO_HS256_SECRET must be set\n".data(using: .utf8)!)
        return 2
    }
    let sub = rest[0]
    if sub == "issue" {
        guard rest.count >= 3 else { return 2 }
        let ttl = rest.count > 3 ? Int64(rest[3]) ?? 3600 : 3600
        let scopes = rest[2].split(separator: ",").map { String($0) }
        let issuer = Issuer(
            algorithm: .hs256, issuer: "iaiso",
            hsKey: secretData, defaultTTLSeconds: ttl)
        do {
            let scope = try issuer.issue(
                subject: rest[1], scopes: scopes, ttlSeconds: ttl)
            print("token: \(scope.token)")
            print("subject: \(scope.subject)")
            print("scopes: \(scope.scopes.joined(separator: ", "))")
            print("jti: \(scope.jti)")
            print("expires_at: \(scope.expiresAt)")
            return 0
        } catch {
            FileHandle.standardError.write("issue failed: \(error)\n".data(using: .utf8)!)
            return 1
        }
    }
    if sub == "verify" {
        guard rest.count == 2 else { return 2 }
        let verifier = Verifier(
            algorithm: .hs256, issuer: "iaiso", hsKey: secretData)
        do {
            let s = try verifier.verify(rest[1])
            print("status: valid")
            print("subject: \(s.subject)")
            print("scopes: \(s.scopes.joined(separator: ", "))")
            print("jti: \(s.jti)")
            print("expires_at: \(s.expiresAt)")
            return 0
        } catch {
            FileHandle.standardError.write("invalid: \(error)\n".data(using: .utf8)!)
            return 1
        }
    }
    return 2
}

func cmdAudit(_ rest: [String]) -> Int32 {
    guard rest.count == 2 else { return 2 }
    guard let data = try? Data(contentsOf: URL(fileURLWithPath: rest[1])),
          let s = String(data: data, encoding: .utf8) else {
        FileHandle.standardError.write("open failed\n".data(using: .utf8)!)
        return 1
    }
    let lines = s.split(separator: "\n", omittingEmptySubsequences: true)
    if rest[0] == "tail" {
        for line in lines {
            if let d = line.data(using: .utf8),
               let obj = try? JSONSerialization.jsonObject(with: d) as? [String: Any] {
                let ts = obj["timestamp"] as? Double ?? 0
                let kind = obj["kind"] as? String ?? "?"
                let exec = obj["execution_id"] as? String ?? "?"
                print(String(format: "%-15.3f  %-28s  %@", ts, kind, exec as NSString))
            }
        }
        return 0
    }
    if rest[0] == "stats" {
        var counts: [String: Int] = [:]
        var executions: Set<String> = []
        var total = 0
        for line in lines {
            guard let d = line.data(using: .utf8),
                  let obj = try? JSONSerialization.jsonObject(with: d) as? [String: Any] else {
                continue
            }
            total += 1
            if let k = obj["kind"] as? String {
                counts[k, default: 0] += 1
            }
            if let e = obj["execution_id"] as? String {
                executions.insert(e)
            }
        }
        print("total events: \(total)")
        print("distinct executions: \(executions.count)")
        for (k, v) in counts.sorted(by: { $0.value > $1.value }) {
            print(String(format: "  %6d  %@", v, k as NSString))
        }
        return 0
    }
    return 2
}

func cmdCoordinator(_ rest: [String]) throws -> Int32 {
    guard rest.first == "demo" else { return 2 }
    let coord = try SharedPressureCoordinator(
        coordinatorId: "cli-demo",
        escalationThreshold: 1.5,
        releaseThreshold: 2.5,
        notifyCooldownSeconds: 0.0,
        aggregator: SumAggregator(),
        auditSink: MemorySink(),
        onEscalation: { s in
            print(String(format: "  [callback] ESCALATION at aggregate=%.3f",
                         s.aggregatePressure))
        },
        onRelease: { s in
            print(String(format: "  [callback] RELEASE at aggregate=%.3f",
                         s.aggregatePressure))
        })
    let workers = ["worker-a", "worker-b", "worker-c"]
    for w in workers { coord.register(w) }
    print("Demo: 3 workers registered. Stepping pressures...")
    let steps: [Double] = [0.3, 0.6, 0.9, 0.6]
    for (i, p) in steps.enumerated() {
        for w in workers { _ = try coord.update(w, pressure: p) }
        let snap = coord.snapshot()
        print(String(format: "  step %d: per-worker=%.2f  aggregate=%.3f  lifecycle=%@",
                     i + 1, p, snap.aggregatePressure, snap.lifecycle.rawValue as NSString))
    }
    return 0
}

func cmdConformance(_ rest: [String]) -> Int32 {
    let specRoot = rest.first ?? "./spec"
    do {
        let r = try ConformanceRunner.runAll(specRoot: specRoot)
        let sections: [(String, [VectorResult])] = [
            ("pressure", r.pressure),
            ("consent", r.consent),
            ("events", r.events),
            ("policy", r.policy),
        ]
        var fail = 0
        for (name, bucket) in sections {
            let pass = bucket.filter { $0.passed }.count
            let total = bucket.count
            let tag = pass == total ? "PASS" : "FAIL"
            if pass != total {
                fail += total - pass
                for v in bucket where !v.passed {
                    print("  [\(name)] \(v.name): \(v.message)")
                }
            }
            print("[\(tag)] \(name): \(pass)/\(total)")
        }
        print("\nconformance: \(r.countPassed())/\(r.countTotal()) vectors passed")
        return fail > 0 ? 1 : 0
    } catch {
        FileHandle.standardError.write("error: \(error)\n".data(using: .utf8)!)
        return 1
    }
}

guard !args.isEmpty, args[0] != "--help", args[0] != "-h" else {
    printHelp()
    exit(args.isEmpty ? 0 : 0)
}

let cmd = args[0]
let rest = Array(args.dropFirst())
let code: Int32

do {
    switch cmd {
    case "policy":      code = cmdPolicy(rest)
    case "consent":     code = cmdConsent(rest)
    case "audit":       code = cmdAudit(rest)
    case "coordinator": code = try cmdCoordinator(rest)
    case "conformance": code = cmdConformance(rest)
    default:
        FileHandle.standardError.write("unknown command: \(cmd)\n".data(using: .utf8)!)
        printHelp()
        code = 2
    }
} catch {
    FileHandle.standardError.write("error: \(error)\n".data(using: .utf8)!)
    code = 1
}
exit(code)
