/**
 * Conformance wrapper — runs every spec vector as an individual test case.
 *
 * This mirrors the Python reference's tests/test_conformance.py and is the
 * authoritative proof that the Node port passes the normative specification.
 */

import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import {
  runConsentVectors,
  runEventsVectors,
  runPolicyVectors,
  runPressureVectors,
  type VectorResult,
} from "../src/conformance/index.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SPEC_ROOT = resolve(__dirname, "..", "spec");

function eachVector(results: VectorResult[], section: string) {
  describe(section, () => {
    for (const r of results) {
      it(r.name, () => {
        expect(r.passed, r.message).toBe(true);
      });
    }
  });
}

eachVector(runPressureVectors(SPEC_ROOT), "pressure");
eachVector(runConsentVectors(SPEC_ROOT), "consent");
eachVector(runEventsVectors(SPEC_ROOT), "events");
eachVector(runPolicyVectors(SPEC_ROOT), "policy");
