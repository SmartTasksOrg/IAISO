---
name: iaiso-spec-conformance-vectors
description: "Use this skill when porting IAIso to a new language, validating an implementation, or debugging a failing vector. Triggers on `vectors.json`, `python -m iaiso.conformance`, `npx iaiso-conformance`, `67/67`. Do not use it to learn the spec itself — load the matching contract skill first."
version: 1.0.0
tier: P0
category: spec
framework: IAIso v5.0
license: See ../LICENSE
---

# IAIso conformance suite — implementation contract

## When this applies

A conformance run is being executed, designed, or debugged.
The 67-vector suite at `core/spec/*/vectors.json` is the
machine-checkable contract every port must pass.

## Steps To Complete

1. **Run the suite from each SDK as documented.**

   ```
   python -m iaiso.conformance core/spec/                 # Python
   npx iaiso-conformance ./spec                            # Node
   go run ./cmd/iaiso-conformance ./spec                   # Go
   cargo run -p iaiso-conformance-bin -- ./spec            # Rust
   ./build.sh test  (or mvn clean test)                    # Java
   dotnet test                                             # C#
   composer test                                           # PHP
   rake test                                               # Ruby
   swift test                                              # Swift
   ```

2. **Read the vector files by subsystem.** Counts as of v1.0:

   | Subsystem  | File                              | Vectors |
   |------------|-----------------------------------|---------|
   | pressure   | `spec/pressure/vectors.json`      | 20      |
   | consent    | `spec/consent/vectors.json`       | 23      |
   | events     | `spec/events/vectors.json`        | 7       |
   | policy     | `spec/policy/vectors.json`        | 17      |
   | total      | —                                 | 67      |

   The coordinator is verified through Redis keyspace tests, not
   JSON vectors.

3. **Triage failures in subsystem order — pressure first.**

   - A pressure failure breaks every subsystem above it; fix
     pressure before anything else.
   - Consent failures are usually scope-grammar or claim-order
     issues.
   - Events failures are usually field-naming or
     serialisation-order drift.
   - Policy failures are usually the cross-field validation
     (`release > escalation`, threshold range, etc.).

4. **Apply the floating-point tolerance, not bit-exactness.**
   Numerics conform when `|p_impl − p_spec| ≤ 1e-9`. Report a
   larger gap as a real bug; don't try to match IEEE-754
   evaluation order across languages.

5. **Hold the vectors stable.** A vector file is normative.
   Vectors are appended at MINOR bumps; existing vectors do
   not change silently. If a port forces a vector edit, that
   is a MAJOR-bump event for the spec, not a fix.

## Common porting bugs

- Threshold check order reversed (`escalation` before
  `release`). Failing vectors typically expect `RELEASED` but
  the impl returns `ESCALATED`.
- Claim-emission order in JWTs differing from the reference
  and breaking byte-equal tests in some vectors.
- Audit event field ordering not matching the spec's documented
  order — relevant for byte-stable archives.
- Coordinator client computing aggregate from non-atomic
  reads (HGETALL outside the Lua script).

## What this skill does NOT cover

- The contracts themselves — load `iaiso-spec-pressure-model`
  etc.
- Adding a new language port — see
  `../iaiso-port-new-language/SKILL.md`.

## References

- `core/spec/README.md` — running the suite, tolerance, stability
- `core/docs/CONFORMANCE.md` — porting workflow
