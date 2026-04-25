import { describe, expect, it } from "vitest";

import {
  ConsentIssuer,
  ConsentVerifier,
  ExpiredToken,
  InsufficientScope,
  InvalidToken,
  RevocationList,
  RevokedToken,
  scopeGranted,
} from "../src/consent/index.js";

const TEST_KEY = "test_key_not_for_production_only_in_unit_tests_abcdefgh12345678";

describe("scopeGranted", () => {
  it("exact matches", () => {
    expect(scopeGranted(["tools.search"], "tools.search")).toBe(true);
  });

  it("prefix at segment boundary", () => {
    expect(scopeGranted(["tools"], "tools.search")).toBe(true);
    expect(scopeGranted(["tools"], "tools.a.b.c")).toBe(true);
  });

  it("does not grant substring-without-boundary", () => {
    expect(scopeGranted(["tools"], "toolsbar")).toBe(false);
  });

  it("does not grant unrelated scopes", () => {
    expect(scopeGranted(["admin"], "tools.search")).toBe(false);
  });

  it("is case sensitive", () => {
    expect(scopeGranted(["Tools"], "tools")).toBe(false);
  });

  it("empty granted list never matches", () => {
    expect(scopeGranted([], "anything")).toBe(false);
  });

  it("throws on empty requested", () => {
    expect(() => scopeGranted(["tools"], "")).toThrow(/non-empty/);
  });
});

describe("ConsentIssuer + ConsentVerifier roundtrip", () => {
  it("issues and verifies a basic token", () => {
    const issuer = new ConsentIssuer({ signing_key: TEST_KEY, algorithm: "HS256" });
    const scope = issuer.issue({ subject: "user-1", scopes: ["tools.search"], ttl_seconds: 60 });

    const verifier = new ConsentVerifier({
      verification_key: TEST_KEY,
      algorithm: "HS256",
      leeway_seconds: 5,
    });
    const verified = verifier.verify(scope.token);
    expect(verified.subject).toBe("user-1");
    expect(verified.scopes).toEqual(["tools.search"]);
    expect(verified.execution_id).toBeNull();
  });

  it("enforces execution binding", () => {
    const issuer = new ConsentIssuer({ signing_key: TEST_KEY, algorithm: "HS256" });
    const scope = issuer.issue({
      subject: "user-1",
      scopes: ["tools.search"],
      ttl_seconds: 60,
      execution_id: "exec-abc",
    });

    const verifier = new ConsentVerifier({
      verification_key: TEST_KEY,
      algorithm: "HS256",
      leeway_seconds: 5,
    });
    expect(() => verifier.verify(scope.token, { execution_id: "exec-wrong" }))
      .toThrow(InvalidToken);
    expect(() => verifier.verify(scope.token, { execution_id: "exec-abc" }))
      .not.toThrow();
  });

  it("raises ExpiredToken when expired", () => {
    // Issue at timestamp 1000, verify at 2000 with 0s leeway, 1s TTL
    const issuer = new ConsentIssuer({
      signing_key: TEST_KEY,
      algorithm: "HS256",
      clock: () => 1000,
    });
    const scope = issuer.issue({ subject: "u", scopes: [], ttl_seconds: 1 });

    const verifier = new ConsentVerifier({
      verification_key: TEST_KEY,
      algorithm: "HS256",
      leeway_seconds: 0,
      clock: () => 2000,
    });
    expect(() => verifier.verify(scope.token)).toThrow(ExpiredToken);
  });

  it("raises RevokedToken when jti is revoked", () => {
    const issuer = new ConsentIssuer({ signing_key: TEST_KEY, algorithm: "HS256" });
    const scope = issuer.issue({ subject: "u", scopes: [], ttl_seconds: 60 });

    const revocation = new RevocationList();
    revocation.revoke(scope.jti);

    const verifier = new ConsentVerifier({
      verification_key: TEST_KEY,
      algorithm: "HS256",
      leeway_seconds: 5,
      revocation_list: revocation,
    });
    expect(() => verifier.verify(scope.token)).toThrow(RevokedToken);
  });
});

describe("ConsentScope.require", () => {
  it("throws InsufficientScope for missing scopes", () => {
    const issuer = new ConsentIssuer({ signing_key: TEST_KEY, algorithm: "HS256" });
    const scope = issuer.issue({ subject: "u", scopes: ["tools.search"], ttl_seconds: 60 });
    expect(() => scope.require("admin")).toThrow(InsufficientScope);
  });

  it("allows granted scopes", () => {
    const issuer = new ConsentIssuer({ signing_key: TEST_KEY, algorithm: "HS256" });
    const scope = issuer.issue({ subject: "u", scopes: ["tools"], ttl_seconds: 60 });
    expect(() => scope.require("tools.search.bulk")).not.toThrow();
  });
});
