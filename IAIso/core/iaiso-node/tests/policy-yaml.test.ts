import { describe, expect, it } from "vitest";
import { writeFileSync, mkdtempSync, rmSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";

import {
  loadPolicyYaml,
  parsePolicyYaml,
  PolicyFormatError,
} from "../src/policy/yaml.js";

describe("parsePolicyYaml", () => {
  it("parses a basic YAML policy", () => {
    const yaml = `
version: "1"
pressure:
  escalation_threshold: 0.8
  release_threshold: 0.95
  token_coefficient: 0.02
coordinator:
  aggregator: mean
  escalation_threshold: 3.0
  release_threshold: 6.0
consent:
  issuer: my-org
  required_scopes:
    - tools.search
    - tools.fetch
metadata:
  owner: platform-team
`;
    const policy = parsePolicyYaml(yaml);
    expect(policy.version).toBe("1");
    expect(policy.pressure.escalation_threshold).toBeCloseTo(0.8, 9);
    expect(policy.pressure.token_coefficient).toBeCloseTo(0.02, 9);
    expect(policy.coordinator.escalation_threshold).toBe(3.0);
    expect(policy.aggregator.name).toBe("mean");
    expect(policy.consent.required_scopes).toEqual(["tools.search", "tools.fetch"]);
    expect(policy.consent.issuer).toBe("my-org");
    expect(policy.metadata).toEqual({ owner: "platform-team" });
  });

  it("rejects YAML failing cross-field validation", () => {
    const yaml = `
version: "1"
pressure:
  escalation_threshold: 0.9
  release_threshold: 0.5
`;
    expect(() => parsePolicyYaml(yaml)).toThrow(/release_threshold/);
  });
});

describe("loadPolicyYaml", () => {
  it("loads .yaml, .yml, and .json extensions", () => {
    const dir = mkdtempSync(join(tmpdir(), "iaiso-yaml-test-"));
    try {
      const yamlPath = join(dir, "p.yaml");
      writeFileSync(yamlPath, 'version: "1"\npressure:\n  escalation_threshold: 0.7\n  release_threshold: 0.9\n');
      const p1 = loadPolicyYaml(yamlPath);
      expect(p1.pressure.escalation_threshold).toBeCloseTo(0.7, 9);

      const ymlPath = join(dir, "p.yml");
      writeFileSync(ymlPath, 'version: "1"\n');
      const p2 = loadPolicyYaml(ymlPath);
      expect(p2.version).toBe("1");

      const jsonPath = join(dir, "p.json");
      writeFileSync(jsonPath, '{"version":"1","pressure":{"escalation_threshold":0.6,"release_threshold":0.8}}');
      const p3 = loadPolicyYaml(jsonPath);
      expect(p3.pressure.release_threshold).toBeCloseTo(0.8, 9);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });

  it("rejects unsupported extensions", () => {
    const dir = mkdtempSync(join(tmpdir(), "iaiso-yaml-test-"));
    try {
      const bad = join(dir, "p.toml");
      writeFileSync(bad, "nope");
      expect(() => loadPolicyYaml(bad)).toThrow(PolicyFormatError);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });
});
