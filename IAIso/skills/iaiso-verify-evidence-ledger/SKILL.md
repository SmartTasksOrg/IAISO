---
name: iaiso-verify-evidence-ledger
description: "Use this skill to produce a SmartFabric evidence-ledger entry: a reproducible, mechanism-level record of an integration (tier, verdicts, logs, isolation attestation, regression, reproduction command) that is safe to share. ALWAYS load this before producing any shareable artifact — it holds the dual-use / coordinated-disclosure rules. Do not use it to publish payloads, name pre-disclosure vulnerable targets, or bypass human sign-off."
version: 1.0.0
tier: P1
category: verify
framework: IAIso v5.0
license: See ../LICENSE
---

# SmartFabric evidence ledger + proof discipline

## When this applies

You are about to produce any artifact a reviewer, OSS maintainer, or
standards body would receive. The ledger is what "verified" means; the
proof discipline is what keeps it responsible. **Load this before emitting
anything shareable.**

## Steps To Complete

1. **Record the ledger entry fields:**
   - Target identity + commit / API version.
   - Integration tier achieved (§4) and therefore the *honest* set of
     layers/invariants enforced (§4.4).
   - Per-sink verdicts (`CONFIRMED` / `DEFENDED` / `NO-FINDING` / `INCONCLUSIVE`).
   - Sandbox logs: provision, build (deps + self-healed packages),
     undefended run, defended run, and the `network=none` isolation
     attestation for the test phase.
   - Regression result: the target's own tests pass post-integration.
   - Reproduction command.
   - Optional: screen recording of build → CONFIRMED → attach control →
     DEFENDED.

2. **Apply the proof discipline (dual-use caution) — NON-NEGOTIABLE.**
   These classes match techniques real adversaries already use, and
   coordinated disclosure is still pending. Therefore:
   - **Benign sentinel only.** No real payloads, agent-manipulation
     recipes, or escape techniques in any shipped artifact.
   - **Anonymize pre-disclosure.** Describe reference findings at mechanism
     level; keep the specific vulnerable target anonymous until coordinated
     disclosure completes.
   - **Neutral, mechanism-based class name** proposed to standards bodies,
     mapped to CWE / OWASP LLM Top-10 / MITRE ATLAS / NIST AI RMF, with
     IAIso credited as the discovering/mitigating framework — never a
     branded class name.
   - **No CVE/finding numbers or named targets go public** before the
     org has been contacted and disclosure is agreed.

3. **Enforce the human sign-off gate.** The machine detects, integrates,
   and verifies. A human authorizes any outbound action — PR, disclosure,
   or deploy. No automated outbound contact, no mass reporting, no
   public-first disclosure. One target at a time, coordinated, guard
   offered as the fix.

4. **Map to IAIso taxonomy.** Each probe is an `iaiso-redteam-*` probe;
   each control is an IAIso layer control (e.g. model-provenance guard =
   Layer 5, invariant #4). Carry the standards mappings IAIso already
   declares.

## What this skill does NOT cover

- Running the verifier — see `iaiso-verify-confirmed-then-defended`.
- Compliance evidence packs for auditors — see `iaiso-compliance-router`.

## References

- `SMARTFABRIC.md`
- `SPEC-iaiso-sandbox-integration.md` §8, §10, §11
