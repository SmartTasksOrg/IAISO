#!/usr/bin/env node
/**
 * IAIso admin CLI.
 *
 * Usage:
 *   iaiso --help
 *
 * Subcommands:
 *   policy validate <file>           — check a policy file for errors
 *   policy template <file>           — write a blank policy template
 *   consent issue <subject> <scope>  — issue a token (requires IAISO_HS256_SECRET)
 *   consent verify <token>           — verify a token against IAISO_HS256_SECRET
 *   audit tail <jsonl-file>          — pretty-print JSONL audit events
 *   audit stats <jsonl-file>         — summarize events by kind
 *   coordinator demo                 — run a short in-memory coordinator demo
 */

import { readFileSync, writeFileSync, createReadStream } from "node:fs";
import { createInterface } from "node:readline";

import { loadPolicy, PolicyError } from "../policy/index.js";
import {
  ConsentIssuer,
  ConsentVerifier,
  ExpiredToken,
  InvalidToken,
  RevokedToken,
} from "../consent/index.js";
import { SharedPressureCoordinator } from "../coordination/memory.js";
import { SumAggregator } from "../policy/index.js";

// ------- helpers -------

function readSecret(): string | null {
  return process.env.IAISO_HS256_SECRET ?? null;
}

function printJson(obj: unknown): void {
  process.stdout.write(JSON.stringify(obj, null, 2) + "\n");
}

// ------- policy -------

function cmdPolicyValidate(args: string[]): number {
  const path = args[0];
  if (!path) {
    process.stderr.write("usage: iaiso policy validate <file>\n");
    return 2;
  }
  try {
    const policy = loadPolicy(path);
    process.stdout.write(`OK: policy v${policy.version}\n`);
    process.stdout.write(
      `  pressure.escalation_threshold = ${policy.pressure.escalation_threshold}\n`,
    );
    process.stdout.write(
      `  coordinator.aggregator        = ${policy.aggregator.name}\n`,
    );
    process.stdout.write(
      `  consent.issuer                = ${policy.consent.issuer}\n`,
    );
    return 0;
  } catch (exc) {
    const err = exc as Error;
    const prefix = err instanceof PolicyError ? "INVALID" : "ERROR";
    process.stderr.write(`${prefix}: ${err.message}\n`);
    return 1;
  }
}

function cmdPolicyTemplate(args: string[]): number {
  const path = args[0];
  if (!path) {
    process.stderr.write("usage: iaiso policy template <file>\n");
    return 2;
  }
  const template = {
    version: "1",
    pressure: {
      escalation_threshold: 0.85,
      release_threshold: 0.95,
      token_coefficient: 0.015,
      tool_coefficient: 0.08,
      depth_coefficient: 0.05,
      dissipation_per_step: 0.02,
      dissipation_per_second: 0.0,
      post_release_lock: true,
    },
    coordinator: {
      aggregator: "sum",
      escalation_threshold: 5.0,
      release_threshold: 8.0,
      notify_cooldown_seconds: 1.0,
    },
    consent: {
      issuer: "iaiso",
      default_ttl_seconds: 3600,
      required_scopes: [],
      allowed_algorithms: ["HS256", "RS256"],
    },
    metadata: {},
  };
  writeFileSync(path, JSON.stringify(template, null, 2) + "\n", "utf8");
  process.stdout.write(`Wrote template to ${path}\n`);
  return 0;
}

// ------- consent -------

function cmdConsentIssue(args: string[]): number {
  const subject = args[0];
  const scopesCsv = args[1];
  if (!subject || !scopesCsv) {
    process.stderr.write(
      "usage: iaiso consent issue <subject> <scope1,scope2,...> [ttl_seconds]\n",
    );
    return 2;
  }
  const secret = readSecret();
  if (!secret) {
    process.stderr.write(
      "error: IAISO_HS256_SECRET must be set in the environment\n",
    );
    return 2;
  }
  const ttl = args[2] ? Number(args[2]) : 3600;
  const scopes = scopesCsv.split(",").map((s) => s.trim()).filter(Boolean);

  const issuer = new ConsentIssuer({ signing_key: secret, algorithm: "HS256" });
  const scope = issuer.issue({ subject, scopes, ttl_seconds: ttl });
  printJson({
    token: scope.token,
    subject: scope.subject,
    scopes: scope.scopes,
    jti: scope.jti,
    expires_at: scope.expires_at,
  });
  return 0;
}

function cmdConsentVerify(args: string[]): number {
  const token = args[0];
  if (!token) {
    process.stderr.write("usage: iaiso consent verify <token>\n");
    return 2;
  }
  const secret = readSecret();
  if (!secret) {
    process.stderr.write(
      "error: IAISO_HS256_SECRET must be set in the environment\n",
    );
    return 2;
  }
  const verifier = new ConsentVerifier({
    verification_key: secret,
    algorithm: "HS256",
  });
  try {
    const verified = verifier.verify(token);
    printJson({
      status: "valid",
      subject: verified.subject,
      scopes: verified.scopes,
      jti: verified.jti,
      expires_at: verified.expires_at,
      execution_id: verified.execution_id,
    });
    return 0;
  } catch (exc) {
    let status = "invalid";
    if (exc instanceof ExpiredToken) status = "expired";
    else if (exc instanceof RevokedToken) status = "revoked";
    else if (exc instanceof InvalidToken) status = "invalid";
    process.stderr.write(`${status}: ${(exc as Error).message}\n`);
    return 1;
  }
}

// ------- audit -------

async function cmdAuditTail(args: string[]): Promise<number> {
  const path = args[0];
  if (!path) {
    process.stderr.write("usage: iaiso audit tail <jsonl-file>\n");
    return 2;
  }
  const rl = createInterface({
    input: createReadStream(path, { encoding: "utf8" }),
    crlfDelay: Infinity,
  });
  for await (const line of rl) {
    const s = line.trim();
    if (!s) continue;
    try {
      const event = JSON.parse(s) as {
        timestamp?: number;
        kind?: string;
        execution_id?: string;
      };
      const ts = event.timestamp
        ? new Date(event.timestamp * 1000).toISOString()
        : "?";
      const kind = (event.kind ?? "?").padEnd(28);
      process.stdout.write(
        `${ts}  ${kind}  ${event.execution_id ?? "?"}\n`,
      );
    } catch {
      process.stdout.write(`  [unparseable] ${s.slice(0, 80)}\n`);
    }
  }
  return 0;
}

async function cmdAuditStats(args: string[]): Promise<number> {
  const path = args[0];
  if (!path) {
    process.stderr.write("usage: iaiso audit stats <jsonl-file>\n");
    return 2;
  }
  const counts = new Map<string, number>();
  const executions = new Set<string>();
  let total = 0;

  const rl = createInterface({
    input: createReadStream(path, { encoding: "utf8" }),
    crlfDelay: Infinity,
  });
  for await (const line of rl) {
    const s = line.trim();
    if (!s) continue;
    try {
      const event = JSON.parse(s) as { kind?: string; execution_id?: string };
      total += 1;
      if (event.kind) counts.set(event.kind, (counts.get(event.kind) ?? 0) + 1);
      if (event.execution_id) executions.add(event.execution_id);
    } catch {
      // ignore
    }
  }

  process.stdout.write(`total events: ${total}\n`);
  process.stdout.write(`distinct executions: ${executions.size}\n`);
  const sorted = [...counts.entries()].sort((a, b) => b[1] - a[1]);
  for (const [kind, count] of sorted) {
    process.stdout.write(`  ${count.toString().padStart(6)}  ${kind}\n`);
  }
  return 0;
}

// ------- coordinator -------

function cmdCoordinatorDemo(): number {
  const coord = new SharedPressureCoordinator({
    coordinator_id: "cli-demo",
    escalation_threshold: 1.5,
    release_threshold: 2.5,
    aggregator: new SumAggregator(),
    notify_cooldown_seconds: 0,
    callbacks: {
      onEscalation: (snap) =>
        process.stdout.write(
          `  [callback] ESCALATION at aggregate=${snap.aggregate_pressure.toFixed(3)}\n`,
        ),
      onRelease: (snap) =>
        process.stdout.write(
          `  [callback] RELEASE at aggregate=${snap.aggregate_pressure.toFixed(3)}\n`,
        ),
    },
  });

  const workers = ["worker-a", "worker-b", "worker-c"];
  for (const w of workers) coord.register(w);

  process.stdout.write("Demo: 3 workers registered. Stepping pressures...\n");
  const script = [0.3, 0.6, 0.9, 0.6];
  for (let step = 0; step < script.length; step++) {
    const perWorker = script[step]!;
    for (const w of workers) coord.update(w, perWorker);
    const snap = coord.snapshot();
    process.stdout.write(
      `  step ${step + 1}: per-worker=${perWorker.toFixed(2)}  aggregate=${snap.aggregate_pressure.toFixed(3)}  lifecycle=${snap.lifecycle}\n`,
    );
  }
  return 0;
}

// ------- main -------

function printHelp(): void {
  process.stdout.write(
    `IAIso admin CLI\n\n` +
    `Subcommands:\n` +
    `  policy validate <file>               check a policy file for errors\n` +
    `  policy template <file>               write a blank policy template\n` +
    `  consent issue <sub> <scope,...> [ttl] issue a token (needs IAISO_HS256_SECRET)\n` +
    `  consent verify <token>               verify a token\n` +
    `  audit tail <jsonl-file>              pretty-print JSONL audit events\n` +
    `  audit stats <jsonl-file>             summarize events by kind\n` +
    `  coordinator demo                     in-memory coordinator smoke test\n` +
    `  conformance <spec-dir>               run the conformance suite (alias for iaiso-conformance)\n`,
  );
}

export async function main(argv: string[] = process.argv.slice(2)): Promise<number> {
  if (argv.length === 0 || argv[0] === "-h" || argv[0] === "--help") {
    printHelp();
    return 0;
  }

  const [group, sub, ...rest] = argv;
  if (group === "policy") {
    if (sub === "validate") return cmdPolicyValidate(rest);
    if (sub === "template") return cmdPolicyTemplate(rest);
  }
  if (group === "consent") {
    if (sub === "issue") return cmdConsentIssue(rest);
    if (sub === "verify") return cmdConsentVerify(rest);
  }
  if (group === "audit") {
    if (sub === "tail") return cmdAuditTail(rest);
    if (sub === "stats") return cmdAuditStats(rest);
  }
  if (group === "coordinator" && sub === "demo") {
    return cmdCoordinatorDemo();
  }
  if (group === "conformance") {
    const { main: confMain } = await import("../conformance/cli.js");
    return confMain([sub ?? "./spec", ...rest].filter(Boolean));
  }

  process.stderr.write(`unknown command: ${argv.join(" ")}\n\n`);
  printHelp();
  return 2;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main().then((code) => process.exit(code));
}
