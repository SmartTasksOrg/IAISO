---
name: iaiso-verify-integration-discovery
description: "Use this skill to discover where IAIso should attach in a cloned open-source target: the dangerous sinks, their reachability ranking, and the recommended integration tier per sink. Do not use it to run the verifier (see iaiso-verify-confirmed-then-defended) or to choose enforcement depth in detail (see iaiso-verify-integration-tiers)."
version: 1.0.0
tier: P1
category: verify
framework: IAIso v5.0
license: See ../LICENSE
---

# SmartFabric integration-point discovery

## When this applies

You have a cloned, authorized open-source target in the sandbox and need
to find where IAIso controls should attach. Discovery is static + dynamic
and reuses the mechanism-detection (windowed AST scan) and loader/shape
detection from the verifier stack.

## Steps To Complete

1. **Scan for the sink categories.** Each maps to an IAIso control and a
   verifier probe. Record file:line for each hit.

   | Sink category | What it is (mechanism level) | IAIso control |
   |---|---|---|
   | Untrusted model provenance | loader with caller-supplied path + remote-code trust | `model_provenance_guard` (Layer 5) |
   | Code / artifact loading | dynamic import / plugin-by-name / agent-chosen package install | consent-scoped load control |
   | Command / argument construction | agent-built shell/SQL/path strings | command/path guards |
   | Config mutation → privileged action | agent writes config/allowlist/.env consumed later by a privileged op | two-stage consent (write-time + use-time) |
   | Resource / endpoint redirection | agent-supplied URL/endpoint → SSRF/exfil | endpoint allowlist (Layer 5) |
   | Tool-result influence | untrusted tool output steers the next agent action | consent re-validation on tool-result-derived actions |

2. **Rank reachability** so you attach where it matters first:
   `server/agent-reachable` > `library-wrappable` > `human-CLI-only`.

3. **Record loader/shape** for model sinks (which loader, expected
   artifact shape). This is what lets the verifier build a *shape-matched
   benign* test artifact later — never a payload.

4. **Recommend a tier per sink** by handing off to
   `iaiso-verify-integration-tiers`. Deeper is better, but record what the
   target actually permits.

5. **Emit the discovery report:** list of sinks, file:line, loader/shape,
   reachability rank, recommended tier. This feeds VERIFY-PRE.

## What this skill does NOT cover

- Running the two-pass verifier — see `iaiso-verify-confirmed-then-defended`.
- Detailed tier→enforcement mapping — see `iaiso-verify-integration-tiers`.
- Building a local mediator for a closed API platform — that platform is
  never cloned; only its documented API is called. See `iaiso-verify-router`.

## References

- `SMARTFABRIC.md`
- `SPEC-iaiso-sandbox-integration.md` §5
