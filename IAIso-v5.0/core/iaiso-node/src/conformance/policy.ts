/**
 * Conformance runner — policy vectors.
 *
 * Validates valid/invalid document handling and per-field expectations.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { buildPolicy, PolicyError } from "../policy/index.js";
import type { VectorResult } from "./pressure.js";

interface PolicyVectorFile {
  version: string;
  tolerance?: number;
  valid: Array<{
    name: string;
    description?: string;
    document: unknown;
    expected_pressure?: Record<string, unknown>;
    expected_coordinator?: Record<string, unknown>;
    expected_consent?: Record<string, unknown>;
    expected_metadata?: Record<string, unknown>;
    expected_aggregator_name?: string;
    expect_loads?: boolean;
  }>;
  invalid: Array<{
    name: string;
    description?: string;
    document: unknown;
    expect_error_path: string;
  }>;
}

function approxEqual(a: unknown, b: unknown, tolerance: number): boolean {
  if (typeof a === "number" && typeof b === "number") {
    return Math.abs(a - b) <= tolerance;
  }
  if (Array.isArray(a) && Array.isArray(b)) {
    return JSON.stringify(a) === JSON.stringify(b);
  }
  if (typeof a === "object" && typeof b === "object" && a !== null && b !== null) {
    return JSON.stringify(a) === JSON.stringify(b);
  }
  return a === b;
}

export function runPolicyVectors(specRoot: string): VectorResult[] {
  const data = JSON.parse(
    readFileSync(join(specRoot, "policy", "vectors.json"), "utf8"),
  ) as PolicyVectorFile;
  const tolerance = data.tolerance ?? 1e-9;
  const results: VectorResult[] = [];

  // Valid
  for (const vec of data.valid ?? []) {
    try {
      const policy = buildPolicy(vec.document);
      const msg = checkValidExpectations(vec, policy, tolerance);
      if (msg === null) {
        results.push({
          section: "policy",
          name: `valid/${vec.name}`,
          passed: true,
          message: "",
        });
      } else {
        results.push({
          section: "policy",
          name: `valid/${vec.name}`,
          passed: false,
          message: msg,
        });
      }
    } catch (exc) {
      results.push({
        section: "policy",
        name: `valid/${vec.name}`,
        passed: false,
        message: `expected success but got ${(exc as Error).name}: ${(exc as Error).message}`,
      });
    }
  }

  // Invalid
  for (const vec of data.invalid ?? []) {
    try {
      buildPolicy(vec.document);
      results.push({
        section: "policy",
        name: `invalid/${vec.name}`,
        passed: false,
        message: "expected PolicyError but loading succeeded",
      });
    } catch (exc) {
      const err = exc as Error;
      if (
        err instanceof PolicyError ||
        err instanceof RangeError ||
        err instanceof TypeError
      ) {
        if (err.message.includes(vec.expect_error_path)) {
          results.push({
            section: "policy",
            name: `invalid/${vec.name}`,
            passed: true,
            message: "",
          });
        } else {
          results.push({
            section: "policy",
            name: `invalid/${vec.name}`,
            passed: false,
            message: `got error ${JSON.stringify(err.message)} but expected path substring ${JSON.stringify(vec.expect_error_path)}`,
          });
        }
      } else {
        results.push({
          section: "policy",
          name: `invalid/${vec.name}`,
          passed: false,
          message: `got unexpected ${err.name}: ${err.message}`,
        });
      }
    }
  }

  return results;
}

function checkValidExpectations(
  vec: PolicyVectorFile["valid"][number],
  policy: ReturnType<typeof buildPolicy>,
  tolerance: number,
): string | null {
  if (vec.expected_pressure) {
    for (const [k, expected] of Object.entries(vec.expected_pressure)) {
      const actual = (policy.pressure as unknown as Record<string, unknown>)[k];
      if (!approxEqual(actual, expected, tolerance)) {
        return `pressure.${k}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`;
      }
    }
  }
  if (vec.expected_coordinator) {
    for (const [k, expected] of Object.entries(vec.expected_coordinator)) {
      const actual = (policy.coordinator as unknown as Record<string, unknown>)[k];
      if (!approxEqual(actual, expected, tolerance)) {
        return `coordinator.${k}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`;
      }
    }
  }
  if (vec.expected_consent) {
    for (const [k, expected] of Object.entries(vec.expected_consent)) {
      const actual = (policy.consent as unknown as Record<string, unknown>)[k];
      if (!approxEqual(actual, expected, tolerance)) {
        return `consent.${k}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`;
      }
    }
  }
  if (vec.expected_aggregator_name !== undefined) {
    if (policy.aggregator.name !== vec.expected_aggregator_name) {
      return `aggregator.name: expected ${JSON.stringify(vec.expected_aggregator_name)}, got ${JSON.stringify(policy.aggregator.name)}`;
    }
  }
  if (vec.expected_metadata !== undefined) {
    if (JSON.stringify(policy.metadata) !== JSON.stringify(vec.expected_metadata)) {
      return `metadata: expected ${JSON.stringify(vec.expected_metadata)}, got ${JSON.stringify(policy.metadata)}`;
    }
  }
  return null;
}
