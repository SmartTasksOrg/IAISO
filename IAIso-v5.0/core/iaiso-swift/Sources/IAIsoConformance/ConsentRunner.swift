import Foundation
import IAIsoConsent

/// Runs the consent section of the conformance suite.
public enum ConsentRunner {

    public static func run(specRoot: String) throws -> [VectorResult] {
        let path = "\(specRoot)/consent/vectors.json"
        let data = try Data(contentsOf: URL(fileURLWithPath: path))
        guard let doc = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return [VectorResult.fail("consent", "load", "could not parse vectors.json")]
        }
        let sharedKeyText = (doc["hs256_key_shared"] as? String) ?? ""
        guard let sharedKey = sharedKeyText.data(using: .utf8) else {
            return [VectorResult.fail("consent", "load", "shared key missing")]
        }

        var out: [VectorResult] = []
        for v in (doc["scope_match"] as? [[String: Any]] ?? []) {
            out.append(runScopeMatch(v))
        }
        for v in (doc["scope_match_errors"] as? [[String: Any]] ?? []) {
            out.append(runScopeMatchError(v))
        }
        for v in (doc["valid_tokens"] as? [[String: Any]] ?? []) {
            out.append(runValidToken(sharedKey: sharedKey, v))
        }
        for v in (doc["invalid_tokens"] as? [[String: Any]] ?? []) {
            out.append(runInvalidToken(sharedKey: sharedKey, v))
        }
        for v in (doc["issue_and_verify_roundtrip"] as? [[String: Any]] ?? []) {
            out.append(runRoundtrip(sharedKey: sharedKey, v))
        }
        return out
    }

    private static func runScopeMatch(_ v: [String: Any]) -> VectorResult {
        let name = "scope_match/\((v["name"] as? String) ?? "?")"
        let granted = (v["granted"] as? [String]) ?? []
        let requested = (v["requested"] as? String) ?? ""
        let want = (v["expected"] as? Bool) ?? false
        do {
            let got = try Scopes.granted(granted, requested)
            return got == want
                ? VectorResult.pass("consent", name)
                : VectorResult.fail("consent", name, "got \(got), want \(want)")
        } catch {
            return VectorResult.fail("consent", name,
                "unexpected exception: \(error)")
        }
    }

    private static func runScopeMatchError(_ v: [String: Any]) -> VectorResult {
        let name = "scope_match_errors/\((v["name"] as? String) ?? "?")"
        let granted = (v["granted"] as? [String]) ?? []
        let requested = (v["requested"] as? String) ?? ""
        let expectErr = (v["expect_error"] as? String) ?? ""
        do {
            _ = try Scopes.granted(granted, requested)
            return VectorResult.fail("consent", name,
                "expected error containing '\(expectErr)', got Ok")
        } catch let err as ScopesError {
            let msg = err.description.lowercased()
            if msg.contains(expectErr.lowercased()) {
                return VectorResult.pass("consent", name)
            }
            return VectorResult.fail("consent", name,
                "expected '\(expectErr)', got: \(err.description)")
        } catch {
            return VectorResult.fail("consent", name,
                "unexpected exception type: \(error)")
        }
    }

    private static func parseAlg(_ v: [String: Any]) -> Algorithm {
        if let s = v["algorithm"] as? String, let a = Algorithm(rawValue: s) {
            return a
        }
        return .hs256
    }

    private static func runValidToken(sharedKey: Data, _ v: [String: Any]) -> VectorResult {
        let name = "valid_tokens/\((v["name"] as? String) ?? "?")"
        let now = Int64((v["now"] as? Int) ?? 0)
        let issuer = (v["issuer"] as? String) ?? "iaiso"
        let alg = parseAlg(v)
        let token = (v["token"] as? String) ?? ""

        let verifier = Verifier(
            algorithm: alg, issuer: issuer, hsKey: sharedKey,
            clock: { now })
        do {
            let scope = try verifier.verify(token)
            guard let exp = v["expected"] as? [String: Any] else {
                return VectorResult.fail("consent", name, "missing expected block")
            }
            if let s = exp["sub"] as? String, scope.subject != s {
                return VectorResult.fail("consent", name, "sub: got \(scope.subject), want \(s)")
            }
            if let j = exp["jti"] as? String, scope.jti != j {
                return VectorResult.fail("consent", name, "jti: got \(scope.jti), want \(j)")
            }
            if let want = exp["scopes"] as? [String] {
                if scope.scopes != want {
                    return VectorResult.fail("consent", name, "scopes mismatch")
                }
            }
            let wantExec = exp["execution_id"] as? String
            if scope.executionId != wantExec {
                return VectorResult.fail("consent", name,
                    "execution_id: got \(scope.executionId ?? "nil"), want \(wantExec ?? "nil")")
            }
            return VectorResult.pass("consent", name)
        } catch {
            return VectorResult.fail("consent", name, "verify failed: \(error)")
        }
    }

    private static func runInvalidToken(sharedKey: Data, _ v: [String: Any]) -> VectorResult {
        let name = "invalid_tokens/\((v["name"] as? String) ?? "?")"
        let now = Int64((v["now"] as? Int) ?? 0)
        let issuer = (v["issuer"] as? String) ?? "iaiso"
        let alg = parseAlg(v)
        let execId = v["execution_id"] as? String
        let expectErr = (v["expect_error"] as? String) ?? ""
        let token = (v["token"] as? String) ?? ""

        let verifier = Verifier(
            algorithm: alg, issuer: issuer, hsKey: sharedKey,
            clock: { now })
        do {
            _ = try verifier.verify(token, requestedExecutionId: execId)
            return VectorResult.fail("consent", name,
                "expected error '\(expectErr)', got Ok")
        } catch let err as ConsentError {
            let actualKind: String
            switch err {
            case .expiredToken: actualKind = "expired"
            case .revokedToken: actualKind = "revoked"
            case .invalidToken: actualKind = "invalid"
            case .insufficientScope: actualKind = "insufficient_scope"
            }
            if actualKind == expectErr {
                return VectorResult.pass("consent", name)
            }
            return VectorResult.fail("consent", name,
                "expected '\(expectErr)', got \(actualKind): \(err.description)")
        } catch {
            return VectorResult.fail("consent", name, "unexpected: \(error)")
        }
    }

    private static func runRoundtrip(sharedKey: Data, _ v: [String: Any]) -> VectorResult {
        let name = "roundtrip/\((v["name"] as? String) ?? "?")"
        guard let issueSpec = v["issue"] as? [String: Any] else {
            return VectorResult.fail("consent", name, "missing issue block")
        }
        let ttl = Int64((issueSpec["ttl_seconds"] as? Int) ?? 3600)
        let subject = (issueSpec["subject"] as? String) ?? ""
        let scopes = (issueSpec["scopes"] as? [String]) ?? []
        let execId = issueSpec["execution_id"] as? String
        let metadata = issueSpec["metadata"] as? [String: Any]
        let now = Int64((v["now"] as? Int) ?? 1_700_000_000)
        let issuer = (v["issuer"] as? String) ?? "iaiso"
        let alg = parseAlg(v)

        let issuerObj = Issuer(
            algorithm: alg, issuer: issuer, hsKey: sharedKey, clock: { now })
        let scope: Scope
        do {
            scope = try issuerObj.issue(
                subject: subject, scopes: scopes,
                executionId: execId, ttlSeconds: ttl, metadata: metadata)
        } catch {
            return VectorResult.fail("consent", name, "issue failed: \(error)")
        }

        let expectSuccess = (v["expected_after_verify_succeeds"] as? Bool) ?? false
        let verifyExec = v["verify_with_execution_id"] as? String

        let verifier = Verifier(
            algorithm: alg, issuer: issuer, hsKey: sharedKey,
            clock: { now + 1 })
        do {
            let verified = try verifier.verify(scope.token, requestedExecutionId: verifyExec)
            if !expectSuccess {
                return VectorResult.fail("consent", name,
                    "expected verify to fail, succeeded")
            }
            if verified.subject != subject {
                return VectorResult.fail("consent", name, "subject mismatch")
            }
            if verified.scopes != scopes {
                return VectorResult.fail("consent", name, "scopes mismatch")
            }
            return VectorResult.pass("consent", name)
        } catch {
            if expectSuccess {
                return VectorResult.fail("consent", name,
                    "expected verify to succeed, failed: \(error)")
            }
            return VectorResult.pass("consent", name)
        }
    }
}
