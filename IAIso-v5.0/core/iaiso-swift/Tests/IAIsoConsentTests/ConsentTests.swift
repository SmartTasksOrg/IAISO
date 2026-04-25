import XCTest
@testable import IAIsoConsent

final class ConsentTests: XCTestCase {
    private let secret = "test_secret_long_enough_for_hs256_security_xx".data(using: .utf8)!

    func testScopeExactMatch() throws {
        XCTAssertTrue(try Scopes.granted(["tools.search"], "tools.search"))
    }

    func testScopePrefixAtBoundary() throws {
        XCTAssertTrue(try Scopes.granted(["tools"], "tools.search"))
    }

    func testScopeSubstringNotBoundary() throws {
        XCTAssertFalse(try Scopes.granted(["tools"], "toolsbar"))
    }

    func testScopeMoreSpecificDoesntSatisfyLessSpecific() throws {
        XCTAssertFalse(try Scopes.granted(["tools.search.bulk"], "tools.search"))
    }

    func testEmptyRequestedThrows() {
        XCTAssertThrowsError(try Scopes.granted(["tools"], ""))
    }

    func testIssueVerifyRoundtrip() throws {
        let issuer = Issuer(
            algorithm: .hs256, issuer: "iaiso", hsKey: secret,
            clock: { 1_700_000_000 })
        let scope = try issuer.issue(
            subject: "user-1", scopes: ["tools.search", "tools.fetch"])
        XCTAssertFalse(scope.token.isEmpty)

        let verifier = Verifier(
            algorithm: .hs256, issuer: "iaiso", hsKey: secret,
            clock: { 1_700_000_001 })
        let verified = try verifier.verify(scope.token)
        XCTAssertEqual(verified.subject, "user-1")
        XCTAssertTrue(try verified.grants("tools.search"))
    }

    func testVerifyRejectsExpired() throws {
        let issuer = Issuer(hsKey: secret, clock: { 1_700_000_000 })
        let scope = try issuer.issue(subject: "u", scopes: ["tools"], ttlSeconds: 1)

        let verifier = Verifier(hsKey: secret, clock: { 1_700_000_010 })
        XCTAssertThrowsError(try verifier.verify(scope.token)) { err in
            if case ConsentError.expiredToken = err {
                // expected
            } else {
                XCTFail("expected expired, got \(err)")
            }
        }
    }

    func testVerifyHonorsRevocation() throws {
        let issuer = Issuer(hsKey: secret, clock: { 1_700_000_000 })
        let scope = try issuer.issue(subject: "u", scopes: ["tools"])
        let rl = RevocationList()
        rl.revoke(scope.jti)

        let verifier = Verifier(
            hsKey: secret, revocationList: rl, clock: { 1_700_000_001 })
        XCTAssertThrowsError(try verifier.verify(scope.token)) { err in
            if case ConsentError.revokedToken = err {
                // expected
            } else {
                XCTFail("expected revoked, got \(err)")
            }
        }
    }

    func testVerifyHonorsExecutionBinding() throws {
        let issuer = Issuer(hsKey: secret, clock: { 1_700_000_000 })
        let scope = try issuer.issue(
            subject: "u", scopes: ["tools"], executionId: "exec-abc")

        let verifier = Verifier(hsKey: secret, clock: { 1_700_000_001 })
        XCTAssertThrowsError(
            try verifier.verify(scope.token, requestedExecutionId: "exec-xyz"))
    }

    func testVerifyRejectsTamperedToken() throws {
        let issuer = Issuer(hsKey: secret, clock: { 1_700_000_000 })
        let scope = try issuer.issue(subject: "u", scopes: ["tools"])
        let tampered = String(scope.token.dropLast(5)) + "XXXXX"

        let verifier = Verifier(hsKey: secret, clock: { 1_700_000_001 })
        XCTAssertThrowsError(try verifier.verify(tampered))
    }

    func testGenerateHS256SecretLength() {
        let s = Issuer.generateHS256Secret()
        XCTAssertGreaterThanOrEqual(s.count, 64)
    }
}
