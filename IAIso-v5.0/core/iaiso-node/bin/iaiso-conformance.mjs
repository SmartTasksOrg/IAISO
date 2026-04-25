#!/usr/bin/env node
/**
 * iaiso-conformance — CLI entry for the Node.js reference SDK.
 *
 * This script is installed as a bin when @iaiso/core is installed. It
 * invokes the compiled conformance runner.
 */
import { main } from "../dist/conformance/cli.js";

main().then((code) => process.exit(code));
