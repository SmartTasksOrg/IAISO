/**
 * Conformance runner — consent vectors.
 *
 * Validates scope matching, valid token verification, invalid token
 * rejection, and issue-and-verify roundtrips.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import {
  ConsentIssuer,
  ConsentVerifier,
  ExpiredToken,
  InvalidToken,
  RevokedToken,
  scopeGranted,
} from "../consent/index.js";
import type { VectorResult } from "./pressure.js";

interface ConsentVectorFile {
  version: string;
  hs256_key_shared: string;
  scope_match: Array<{
    name: string;
    granted: string[];
    requested: string;
    expected: boolean;
  }>;
  scope_match_errors: Array<{
    name: string;
    granted: string[];
    requested: string;
    expect_error: string;
  }>;
  valid_tokens: Array<{
    name: string;
    description?: string;
    token: string;
    algorithm: "HS256" | "RS256";
    issuer: string;
    now: number;
    execution_id?: string | null;
    expected: {
      sub: string;
      jti: string;
      scopes: string[];
      execution_id: string | null;
      metadata: Record<string, unknown>;
    };
  }>;
  invalid_tokens: Array<{
    name: string;
    description?: string;
    token: string;
    algorithm: "HS256" | "RS256";
    issuer: string;
    now: number;
    execution_id?: string | null;
    expect_error: "expired" | "invalid" | "revoked";
  }>;
  issue_and_verify_roundtrip: Array<{
    name: string;
    description?: string;
    issue: {
      subject: string;
      scopes: string[];
      ttl_seconds: number;
      execution_id: string | null;
      metadata: Record<string, unknown> | null;
    };
    verify_with_execution_id?: string;
    expected_after_issue: {
      subject: string;
      scopes: string[];
      execution_id: string | null;
    };
    expected_after_verify_succeeds: boolean;
  }>;
}

const errorMap = {
  expired: ExpiredToken,
  invalid: InvalidToken,
  revoked: RevokedToken,
} as const;

export function runConsentVectors(specRoot: string): VectorResult[] {
  const data = JSON.parse(
    readFileSync(join(specRoot, "consent", "vectors.json"), "utf8"),
  ) as ConsentVectorFile;
  const sharedKey = data.hs256_key_shared;
  const results: VectorResult[] = [];

  // 1. scope_match
  for (const vec of data.scope_match ?? []) {
    const got = scopeGranted(vec.granted, vec.requested);
    if (got === vec.expected) {
      results.push({
        section: "consent",
        name: `scope_match/${vec.name}`,
        passed: true,
        message: "",
      });
    } else {
      results.push({
        section: "consent",
        name: `scope_match/${vec.name}`,
        passed: false,
        message: `expected ${JSON.stringify(vec.expected)}, got ${JSON.stringify(got)}`,
      });
    }
  }

  // 2. scope_match_errors
  for (const vec of data.scope_match_errors ?? []) {
    try {
      scopeGranted(vec.granted, vec.requested);
      results.push({
        section: "consent",
        name: `scope_match_error/${vec.name}`,
        passed: false,
        message: "expected error but call succeeded",
      });
    } catch (exc) {
      const msg = (exc as Error).message;
      if (msg.includes(vec.expect_error)) {
        results.push({
          section: "consent",
          name: `scope_match_error/${vec.name}`,
          passed: true,
          message: "",
        });
      } else {
        results.push({
          section: "consent",
          name: `scope_match_error/${vec.name}`,
          passed: false,
          message: `got error ${JSON.stringify(msg)} but expected substring ${JSON.stringify(vec.expect_error)}`,
        });
      }
    }
  }

  // 3. valid_tokens
  for (const vec of data.valid_tokens ?? []) {
    const verifier = new ConsentVerifier({
      verification_key: sharedKey,
      algorithm: vec.algorithm,
      issuer: vec.issuer,
      leeway_seconds: 0,
      clock: () => vec.now,
    });
    try {
      const scope = verifier.verify(vec.token, {
        execution_id: vec.execution_id ?? null,
      });
      const e = vec.expected;
      const mismatches: string[] = [];
      if (scope.subject !== e.sub)
        mismatches.push(`subject ${JSON.stringify(scope.subject)} != ${JSON.stringify(e.sub)}`);
      if (scope.jti !== e.jti)
        mismatches.push(`jti ${JSON.stringify(scope.jti)} != ${JSON.stringify(e.jti)}`);
      if (JSON.stringify(scope.scopes) !== JSON.stringify(e.scopes))
        mismatches.push(`scopes ${JSON.stringify(scope.scopes)} != ${JSON.stringify(e.scopes)}`);
      if (scope.execution_id !== e.execution_id)
        mismatches.push(`execution_id ${JSON.stringify(scope.execution_id)} != ${JSON.stringify(e.execution_id)}`);
      if (JSON.stringify(scope.metadata) !== JSON.stringify(e.metadata))
        mismatches.push(`metadata ${JSON.stringify(scope.metadata)} != ${JSON.stringify(e.metadata)}`);

      if (mismatches.length === 0) {
        results.push({
          section: "consent",
          name: `valid_token/${vec.name}`,
          passed: true,
          message: "",
        });
      } else {
        results.push({
          section: "consent",
          name: `valid_token/${vec.name}`,
          passed: false,
          message: mismatches.join("; "),
        });
      }
    } catch (exc) {
      results.push({
        section: "consent",
        name: `valid_token/${vec.name}`,
        passed: false,
        message: `verification failed: ${(exc as Error).name}: ${(exc as Error).message}`,
      });
    }
  }

  // 4. invalid_tokens
  for (const vec of data.invalid_tokens ?? []) {
    const verifier = new ConsentVerifier({
      verification_key: sharedKey,
      algorithm: vec.algorithm,
      issuer: vec.issuer,
      leeway_seconds: 0,
      clock: () => vec.now,
    });
    const expectedCls = errorMap[vec.expect_error];
    try {
      verifier.verify(vec.token, { execution_id: vec.execution_id ?? null });
      results.push({
        section: "consent",
        name: `invalid_token/${vec.name}`,
        passed: false,
        message: `expected ${expectedCls.name} but verify succeeded`,
      });
    } catch (exc) {
      if (exc instanceof expectedCls) {
        results.push({
          section: "consent",
          name: `invalid_token/${vec.name}`,
          passed: true,
          message: "",
        });
      } else {
        results.push({
          section: "consent",
          name: `invalid_token/${vec.name}`,
          passed: false,
          message: `expected ${expectedCls.name} but got ${(exc as Error).name}: ${(exc as Error).message}`,
        });
      }
    }
  }

  // 5. issue_and_verify_roundtrip
  for (const vec of data.issue_and_verify_roundtrip ?? []) {
    const issuer = new ConsentIssuer({
      signing_key: sharedKey,
      algorithm: "HS256",
      issuer: "iaiso",
    });

    try {
      const scope = issuer.issue({
        subject: vec.issue.subject,
        scopes: vec.issue.scopes,
        execution_id: vec.issue.execution_id,
        ttl_seconds: vec.issue.ttl_seconds,
        metadata: vec.issue.metadata ?? undefined,
      });
      const exp = vec.expected_after_issue;
      const mismatches: string[] = [];
      if (scope.subject !== exp.subject) mismatches.push("subject mismatch");
      if (JSON.stringify(scope.scopes) !== JSON.stringify(exp.scopes))
        mismatches.push("scopes mismatch");
      if (scope.execution_id !== exp.execution_id)
        mismatches.push("execution_id mismatch");

      if (mismatches.length > 0) {
        results.push({
          section: "consent",
          name: `roundtrip/${vec.name}`,
          passed: false,
          message: mismatches.join("; "),
        });
        continue;
      }

      const verifier = new ConsentVerifier({
        verification_key: sharedKey,
        algorithm: "HS256",
        issuer: "iaiso",
        leeway_seconds: 5,
      });
      verifier.verify(scope.token, {
        execution_id: vec.verify_with_execution_id ?? null,
      });
      results.push({
        section: "consent",
        name: `roundtrip/${vec.name}`,
        passed: true,
        message: "",
      });
    } catch (exc) {
      results.push({
        section: "consent",
        name: `roundtrip/${vec.name}`,
        passed: false,
        message: `roundtrip failed: ${(exc as Error).name}: ${(exc as Error).message}`,
      });
    }
  }

  return results;
}
