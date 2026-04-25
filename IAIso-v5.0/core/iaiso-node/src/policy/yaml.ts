/**
 * YAML policy loader.
 *
 * Extends the JSON loader with YAML support via `js-yaml`.
 * Install:
 *   npm install js-yaml
 *
 * Usage:
 *   import { loadPolicyYaml } from "@iaiso/core/policy/yaml";
 *   const policy = loadPolicyYaml("./iaiso.policy.yaml");
 */

import { readFileSync } from "node:fs";
import { extname } from "node:path";
import { load as yamlLoad } from "js-yaml";

import { buildPolicy } from "./index.js";
import type { Policy } from "./index.js";

export class PolicyFormatError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "PolicyFormatError";
  }
}

/** Load a policy from a JSON or YAML file on disk. */
export function loadPolicyYaml(path: string): Policy {
  const raw = readFileSync(path, "utf8");
  const ext = extname(path).toLowerCase();
  let doc: unknown;

  if (ext === ".json") {
    doc = JSON.parse(raw);
  } else if (ext === ".yaml" || ext === ".yml") {
    doc = yamlLoad(raw);
  } else {
    throw new PolicyFormatError(
      `Unsupported policy file extension: ${ext} (expected .json, .yaml, or .yml)`,
    );
  }

  return buildPolicy(doc);
}

/** Parse a YAML string into a Policy. */
export function parsePolicyYaml(yaml: string): Policy {
  const doc = yamlLoad(yaml);
  return buildPolicy(doc);
}
