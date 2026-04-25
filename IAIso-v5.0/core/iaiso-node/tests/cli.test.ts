import { describe, expect, it, beforeEach, afterEach, vi } from "vitest";
import { mkdtempSync, writeFileSync, rmSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";

import { main } from "../src/cli/index.js";

let stdoutChunks: string[];
let stderrChunks: string[];
let origStdoutWrite: typeof process.stdout.write;
let origStderrWrite: typeof process.stderr.write;
let origSecret: string | undefined;

beforeEach(() => {
  stdoutChunks = [];
  stderrChunks = [];
  origStdoutWrite = process.stdout.write.bind(process.stdout);
  origStderrWrite = process.stderr.write.bind(process.stderr);
  // Capture writes
  (process.stdout.write as unknown as (s: string) => boolean) = ((s: string) => {
    stdoutChunks.push(s);
    return true;
  }) as unknown as typeof process.stdout.write;
  (process.stderr.write as unknown as (s: string) => boolean) = ((s: string) => {
    stderrChunks.push(s);
    return true;
  }) as unknown as typeof process.stderr.write;
  origSecret = process.env.IAISO_HS256_SECRET;
});

afterEach(() => {
  process.stdout.write = origStdoutWrite;
  process.stderr.write = origStderrWrite;
  if (origSecret === undefined) delete process.env.IAISO_HS256_SECRET;
  else process.env.IAISO_HS256_SECRET = origSecret;
});

describe("iaiso CLI", () => {
  it("shows help when no args given", async () => {
    const code = await main([]);
    expect(code).toBe(0);
    expect(stdoutChunks.join("")).toContain("IAIso admin CLI");
  });

  it("policy template writes a valid template that validates", async () => {
    const dir = mkdtempSync(join(tmpdir(), "iaiso-cli-test-"));
    try {
      const path = join(dir, "p.json");
      const tcode = await main(["policy", "template", path]);
      expect(tcode).toBe(0);

      const vcode = await main(["policy", "validate", path]);
      expect(vcode).toBe(0);
      expect(stdoutChunks.join("")).toContain("OK: policy v1");
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });

  it("policy validate returns 1 on bad policy", async () => {
    const dir = mkdtempSync(join(tmpdir(), "iaiso-cli-test-"));
    try {
      const path = join(dir, "bad.json");
      writeFileSync(path, '{"version":"2"}');
      const code = await main(["policy", "validate", path]);
      expect(code).toBe(1);
      expect(stderrChunks.join("")).toMatch(/INVALID/);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });

  it("consent issue + consent verify roundtrip", async () => {
    process.env.IAISO_HS256_SECRET = "test_secret_abcdefg0123456789012345";

    const issueCode = await main([
      "consent",
      "issue",
      "user-42",
      "tools.search,tools.fetch",
      "60",
    ]);
    expect(issueCode).toBe(0);
    const issued = JSON.parse(stdoutChunks.join(""));
    expect(issued.subject).toBe("user-42");
    expect(issued.scopes).toEqual(["tools.search", "tools.fetch"]);

    // Reset buffer
    stdoutChunks.length = 0;
    const verifyCode = await main(["consent", "verify", issued.token]);
    expect(verifyCode).toBe(0);
    const verified = JSON.parse(stdoutChunks.join(""));
    expect(verified.status).toBe("valid");
    expect(verified.subject).toBe("user-42");
  });

  it("consent issue errors without IAISO_HS256_SECRET", async () => {
    delete process.env.IAISO_HS256_SECRET;
    const code = await main(["consent", "issue", "u", "s"]);
    expect(code).toBe(2);
    expect(stderrChunks.join("")).toContain("IAISO_HS256_SECRET");
  });

  it("audit stats counts events correctly", async () => {
    const dir = mkdtempSync(join(tmpdir(), "iaiso-cli-test-"));
    try {
      const path = join(dir, "audit.jsonl");
      const events = [
        { kind: "engine.init", execution_id: "a", timestamp: 1700000000 },
        { kind: "engine.step", execution_id: "a", timestamp: 1700000001 },
        { kind: "engine.step", execution_id: "a", timestamp: 1700000002 },
        { kind: "engine.step", execution_id: "b", timestamp: 1700000003 },
        { kind: "engine.release", execution_id: "a", timestamp: 1700000004 },
      ];
      writeFileSync(
        path,
        events.map((e) => JSON.stringify(e)).join("\n") + "\n",
      );
      const code = await main(["audit", "stats", path]);
      expect(code).toBe(0);
      const out = stdoutChunks.join("");
      expect(out).toContain("total events: 5");
      expect(out).toContain("distinct executions: 2");
      expect(out).toContain("engine.step");
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });

  it("coordinator demo runs and emits escalation/release callbacks", async () => {
    const code = await main(["coordinator", "demo"]);
    expect(code).toBe(0);
    const out = stdoutChunks.join("");
    expect(out).toContain("3 workers registered");
    expect(out).toMatch(/ESCALATION|RELEASE/);
  });

  it("unknown command returns 2 and prints help", async () => {
    const code = await main(["nonsense"]);
    expect(code).toBe(2);
    expect(stderrChunks.join("")).toContain("unknown command");
  });
});
