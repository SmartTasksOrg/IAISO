---
name: iaiso-port-conformance-runner
description: "Use this skill when implementing the conformance runner for a new port. Do not use it for the SDK itself — see `iaiso-port-new-language`."
version: 1.0.0
tier: P3
category: porting
framework: IAIso v5.0
license: See ../LICENSE
---

# Implementing a conformance runner

## When this applies

The new port needs a CLI / entry point that executes the 67
vectors and reports pass/fail.

## Steps To Complete

1. **Match the existing CLI shape.** Every port exposes
   `iaiso conformance run <spec-dir>`. Match it.

2. **Implement vector loading.** The vector files are JSON;
   use the language's standard parser. Each subsystem's
   file is a flat list of cases.

3. **Apply tolerance correctly.** `|p_impl − p_spec| ≤ 1e-9`
   for floats. Bit-exact for byte arrays. String-equal for
   JWT claims.

4. **Report failures with locator info.** Vector index,
   subsystem, expected vs actual. A failure that just says
   "vector 5 failed" wastes hours.

5. **Make it CI-friendly.** Exit code 0 on 67/67 pass,
   non-zero on any failure. Print a one-line summary
   (`67/67 vectors pass`) so CI logs are scannable.

## What this skill does NOT cover

- Vector content — see
  `../iaiso-spec-conformance-vectors/SKILL.md`.

## References

- `core/iaiso-python/iaiso/conformance/__main__.py`
- `core/iaiso-go/cmd/iaiso-conformance/`
