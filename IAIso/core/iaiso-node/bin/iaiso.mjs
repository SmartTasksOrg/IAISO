#!/usr/bin/env node
/**
 * iaiso — admin CLI entry point.
 * Delegates to the compiled CLI under dist/.
 */
import { main } from "../dist/cli/index.js";

main().then((code) => process.exit(code));
