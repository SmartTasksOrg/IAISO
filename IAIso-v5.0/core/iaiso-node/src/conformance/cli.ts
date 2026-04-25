#!/usr/bin/env node
/**
 * IAIso conformance CLI for the Node reference implementation.
 *
 * Usage:
 *   node src/conformance/cli.ts [spec_dir]
 *   node src/conformance/cli.ts spec/ --section pressure
 *   node src/conformance/cli.ts spec/ --verbose
 */

import { existsSync } from "node:fs";
import { resolve } from "node:path";

import {
  runConsentVectors,
  runEventsVectors,
  runPolicyVectors,
  runPressureVectors,
  type VectorResult,
} from "./index.js";

function parseArgs(argv: string[]): {
  specDir: string;
  section: string;
  verbose: boolean;
} {
  let specDir = "spec";
  let section = "all";
  let verbose = false;

  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]!;
    if (a === "--section") {
      section = argv[++i] ?? "all";
    } else if (a === "-v" || a === "--verbose") {
      verbose = true;
    } else if (!a.startsWith("--")) {
      specDir = a;
    }
  }

  return { specDir, section, verbose };
}

export async function main(argv: string[] = process.argv.slice(2)): Promise<number> {
  const { specDir, section, verbose } = parseArgs(argv);
  const specRoot = resolve(specDir);

  if (!existsSync(specRoot)) {
    process.stderr.write(`error: spec directory not found: ${specRoot}\n`);
    return 2;
  }

  const runners: Array<[string, (r: string) => VectorResult[]]> = [
    ["pressure", runPressureVectors],
    ["consent", runConsentVectors],
    ["events", runEventsVectors],
    ["policy", runPolicyVectors],
  ];

  const selected =
    section === "all" ? runners : runners.filter(([n]) => n === section);

  let total = 0;
  let failed = 0;

  for (const [name, runner] of selected) {
    let results: VectorResult[];
    try {
      results = runner(specRoot);
    } catch (exc) {
      const err = exc as NodeJS.ErrnoException;
      if (err.code === "ENOENT") {
        process.stdout.write(`[skip] ${name}: ${err.message}\n`);
        continue;
      }
      throw exc;
    }

    const sectionFail = results.filter((r) => !r.passed).length;
    total += results.length;
    failed += sectionFail;

    const status = sectionFail === 0 ? "PASS" : "FAIL";
    process.stdout.write(
      `[${status}] ${name}: ${results.length - sectionFail}/${results.length}\n`,
    );

    for (const r of results) {
      if (verbose || !r.passed) {
        const icon = r.passed ? "✓" : "✗";
        const msg = r.message ? `: ${r.message}` : "";
        process.stdout.write(`    ${icon} ${r.section}/${r.name}${msg}\n`);
      }
    }
  }

  process.stdout.write("\n");
  if (failed === 0) {
    process.stdout.write(`conformance: all ${total} vectors passed\n`);
    return 0;
  }
  process.stdout.write(`conformance: ${failed}/${total} vectors failed\n`);
  return 1;
}

// Direct invocation
if (import.meta.url === `file://${process.argv[1]}`) {
  main().then((code) => process.exit(code));
}
