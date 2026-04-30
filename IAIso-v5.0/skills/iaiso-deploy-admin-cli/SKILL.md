---
name: iaiso-deploy-admin-cli
description: "Use this skill when running operator workflows via the `iaiso` CLI. Triggers on `policy validate`, `consent issue`, `audit tail`, `coordinator inspect`, `conformance run`. Do not use it for SDK code paths — those have language-specific skills."
version: 1.0.0
tier: P1
category: deploy
framework: IAIso v5.0
license: See ../LICENSE
---

# The IAIso admin CLI

## When this applies

Operations work — validating a policy, issuing a one-off
consent token, tailing audit, inspecting the coordinator,
running conformance.

## Steps To Complete

1. **Know the entry points per language:**

   - Python: `python -m iaiso ...` or `iaiso ...` (after
     install)
   - Node:  `npx iaiso ...`
   - Go:    `iaiso ...` (built binary from `cmd/iaiso`)
   - Rust:  `iaiso ...` (cargo install or compiled)
   - Java:  `java -jar iaiso-cli.jar ...`
   - C#:    `dotnet run --project src/Iaiso.Cli`
   - PHP:   `./bin/iaiso ...`
   - Ruby:  `./exe/iaiso ...`

   All implement the same subcommand surface.

2. **Validate policies before deploying.**

   ```
   iaiso policy validate path/to/policy.yaml
   ```

   Errors print a JSON-Pointer-like path. The `--template`
   flag prints a fully-annotated minimal policy.

3. **Issue and verify consent tokens.**

   ```
   iaiso consent issue --subject alice --scopes tools.read --ttl 1800
   iaiso consent verify <token>
   ```

   Use this for one-off tokens (debugging, demos). For
   production issuance, use the SDK's Issuer programmatically.

4. **Tail audit events.**

   ```
   iaiso audit tail --kind 'engine.*'
   iaiso audit tail --execution-id exec-abc-123
   ```

   Filter by kind glob or execution. For exporting a
   window for compliance, see
   `iaiso-audit-trail-export`.

5. **Inspect the coordinator.**

   ```
   iaiso coordinator inspect --redis redis://prod:6379 \
     --prefix iaiso:coord --id agents
   ```

   Prints the per-execution pressures and aggregate. Use
   this when diagnosing fleet-pressure mysteries.

6. **Run conformance against a spec directory.**

   ```
   iaiso conformance run core/spec/
   ```

   Use in CI for ports — see
   `iaiso-spec-conformance-vectors`.

## What this skill does NOT cover

- SDK programmatic use — load the matching language skill.
- Coordinator deployment — see
  `../iaiso-deploy-coordinator-redis/SKILL.md`.

## References

- top-level `README.md` quick-start blocks per language
