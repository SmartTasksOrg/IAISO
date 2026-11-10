---
name: iaiso-verify-router
description: "Use this skill when integrating IAIso into a target system via the SmartFabric sandbox pipeline (acquire, discover, tier, verify, ledger, sign-off). Routes to the right SmartFabric skill. Do not use it as the answer; always route on. Do not use it for running under IAIso (that is iaiso-runtime-*) or for adversarial probing of an existing deployment (that is iaiso-redteam-*)."
version: 1.0.0
tier: P1
category: verify
framework: IAIso v5.0
license: See ../LICENSE
---

# IAIso SmartFabric verification router

## When this applies

You are bringing IAIso controls into a target system and want to
*prove* — not assert — that the control holds. SmartFabric is the
sandbox-mediated integration-and-verification protocol described in
`SMARTFABRIC.md`. It answers three questions mechanically: where can
IAIso attach, at what depth, and does the attached control actually hold.

Scope is defensive and authorized only: your own repos, OSS under
coordinated disclosure, and closed platforms exercised solely through
their documented APIs via a local mediator you build.

## Steps To Complete

1. **Confirm authorization and scope first.** Only your own boundary.
   Never adversarially probe a live third-party service — build a local
   API mediator instead. Read the responsible-use rules in
   `iaiso-verify-evidence-ledger` before producing any artifact.

2. **Match the stage to the skill:**

   | Stage | Skill |
   |-------|-------|
   | Find where IAIso should attach (sinks, reachability) | `iaiso-verify-integration-discovery` |
   | Choose the deepest attachable tier + honest enforcement map | `iaiso-verify-integration-tiers` |
   | Run the two-pass confirmed-then-defended verifier | `iaiso-verify-confirmed-then-defended` |
   | Guarantee isolation (`network=none`) + self-healing deps | `iaiso-verify-sandbox-isolation` |
   | Produce the reproducible, disclosure-safe ledger entry | `iaiso-verify-evidence-ledger` |
   | The model-provenance control itself | `iaiso-runtime-model-provenance-guard` |
   | The model-provenance red-team probe | `iaiso-redteam-model-provenance` |
   | Snap-in middleware when no clean hook exists | `iaiso-integ-middleware-reference` |

3. **Enforce the human sign-off gate.** Machine detects, integrates, and
   verifies; a human authorizes any outbound action (PR, disclosure,
   deploy). This is non-negotiable — see `iaiso-verify-evidence-ledger`.

## What this skill does NOT cover

- Substantive stage content — always route on.
- Running *under* IAIso at agent runtime — see `iaiso-runtime-governed-agent`.
- Adversarial assessment of an existing deployment — see `iaiso-redteam-router`.

## References

- `SMARTFABRIC.md`
- `SPEC-iaiso-sandbox-integration.md`
