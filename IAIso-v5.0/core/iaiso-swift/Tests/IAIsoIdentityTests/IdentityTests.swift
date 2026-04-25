import XCTest
@testable import IAIsoConsent
@testable import IAIsoIdentity

final class IdentityTests: XCTestCase {

    func testDeriveDirectClaimString() {
        let out = OidcVerifier.deriveScopes(
            ["scope": "tools.search tools.fetch"],
            mapping: .defaults)
        XCTAssertTrue(out.contains("tools.search"))
        XCTAssertTrue(out.contains("tools.fetch"))
    }

    func testDeriveDirectClaimArray() {
        let out = OidcVerifier.deriveScopes(
            ["scp": ["a.b", "c"]],
            mapping: .defaults)
        XCTAssertTrue(out.contains("a.b"))
        XCTAssertTrue(out.contains("c"))
    }

    func testDeriveGroupToScopes() {
        let out = OidcVerifier.deriveScopes(
            ["groups": ["engineers"]],
            mapping: ScopeMapping(
                groupToScopes: ["engineers": ["tools.search", "tools.fetch"]]))
        XCTAssertTrue(out.contains("tools.search"))
        XCTAssertTrue(out.contains("tools.fetch"))
    }

    func testAlwaysGrantAdded() {
        let out = OidcVerifier.deriveScopes(
            [:],
            mapping: ScopeMapping(alwaysGrant: ["base"]))
        XCTAssertEqual(out, ["base"])
    }

    func testPresetsHaveExpectedEndpoints() {
        let okta = ProviderConfig.okta(domain: "acme.okta.com", audience: "api")
        XCTAssertTrue(okta.discoveryURL!.contains("acme.okta.com"))

        let auth0 = ProviderConfig.auth0(domain: "acme.auth0.com", audience: "api")
        XCTAssertTrue(auth0.issuer!.hasSuffix("/"))

        let azure = ProviderConfig.azureAd(tenant: "tenant-id", audience: "api", v2: true)
        XCTAssertTrue(azure.discoveryURL!.contains("v2.0"))
    }

    func testVerifyFailsWhenJwksNotLoaded() {
        let v = OidcVerifier(config: .defaults)
        XCTAssertThrowsError(try v.verify("a.b.c"))
    }
}
