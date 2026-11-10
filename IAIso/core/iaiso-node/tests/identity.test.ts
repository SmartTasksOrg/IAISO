import { describe, expect, it } from "vitest";

import {
  auth0Config,
  azureAdConfig,
  deriveScopes,
  oktaConfig,
  OIDCError,
  OIDCVerifier,
} from "../src/identity/index.js";

describe("provider config factories", () => {
  it("oktaConfig assembles issuer + discovery URL", () => {
    const cfg = oktaConfig({
      domain: "example.okta.com",
      audience: "api://default",
    });
    expect(cfg.issuer).toBe("https://example.okta.com");
    expect(cfg.discoveryUrl).toBe(
      "https://example.okta.com/.well-known/openid-configuration",
    );
    expect(cfg.audience).toBe("api://default");
    expect(cfg.allowedAlgorithms).toEqual(["RS256"]);
  });

  it("auth0Config uses trailing-slash issuer convention", () => {
    const cfg = auth0Config({ domain: "acme.auth0.com" });
    expect(cfg.issuer).toBe("https://acme.auth0.com/");
    expect(cfg.discoveryUrl).toBe(
      "https://acme.auth0.com/.well-known/openid-configuration",
    );
  });

  it("azureAdConfig defaults to v2 endpoint", () => {
    const cfg = azureAdConfig({
      tenant: "aaaa-bbbb-cccc",
      audience: "api://iaiso",
    });
    expect(cfg.issuer).toBe(
      "https://login.microsoftonline.com/aaaa-bbbb-cccc/v2.0",
    );
    expect(cfg.discoveryUrl).toContain("/v2.0/.well-known/openid-configuration");
  });

  it("azureAdConfig v1 with v2:false", () => {
    const cfg = azureAdConfig({ tenant: "t", v2: false });
    expect(cfg.issuer).toBe("https://login.microsoftonline.com/t");
    expect(cfg.discoveryUrl).toBe(
      "https://login.microsoftonline.com/t/.well-known/openid-configuration",
    );
  });
});

describe("deriveScopes", () => {
  it("parses space-separated scope claim", () => {
    const scopes = deriveScopes({ scope: "tools.search tools.fetch" });
    expect(scopes.sort()).toEqual(["tools.fetch", "tools.search"]);
  });

  it("parses array-form permissions claim", () => {
    const scopes = deriveScopes(
      { permissions: ["admin", "read:data"] },
      { directClaims: ["permissions"] },
    );
    expect(scopes.sort()).toEqual(["admin", "read:data"]);
  });

  it("maps groups to scopes", () => {
    const scopes = deriveScopes(
      { groups: ["engineers", "admins"] },
      {
        directClaims: [],
        groupToScopes: {
          engineers: ["tools.search", "tools.fetch"],
          admins: ["admin"],
        },
      },
    );
    expect(new Set(scopes)).toEqual(new Set(["tools.search", "tools.fetch", "admin"]));
  });

  it("adds alwaysGrant to every user", () => {
    const scopes = deriveScopes(
      {},
      { directClaims: [], alwaysGrant: ["tools.ping"] },
    );
    expect(scopes).toEqual(["tools.ping"]);
  });

  it("deduplicates overlapping scopes", () => {
    const scopes = deriveScopes(
      { scope: "tools.search tools.search" },
    );
    expect(scopes).toEqual(["tools.search"]);
  });
});

describe("OIDCVerifier construction", () => {
  it("requires either discoveryUrl or jwksUrl", () => {
    expect(() => new OIDCVerifier({})).toThrow(OIDCError);
  });

  it("accepts jwksUrl without discovery", () => {
    expect(() => new OIDCVerifier({ jwksUrl: "https://idp.example.com/jwks" }))
      .not.toThrow();
  });
});
