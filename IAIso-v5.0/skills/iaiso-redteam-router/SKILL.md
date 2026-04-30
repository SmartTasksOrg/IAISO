---
name: iaiso-redteam-router
description: "Use this skill when starting an adversarial evaluation of an IAIso deployment. Routes to the right probe family. Do not use it as the answer; always route on."
version: 1.0.0
tier: P3
category: redteam
framework: IAIso v5.0
license: See ../LICENSE
---

# IAIso red-team router

## When this applies

Authorised adversarial assessment of an IAIso deployment.
Pick the probe family that matches the threat model.

## Steps To Complete

1. **Match the threat to the probe skill:**

   | Threat                                    | Skill                                  |
   |-------------------------------------------|----------------------------------------|
   | Agent gaming pressure (proxy optimization)| `iaiso-redteam-pressure-gaming`        |
   | Confused-deputy / scope confusion         | `iaiso-redteam-consent-confusion`      |
   | Coordinator hash poisoning                | `iaiso-redteam-coordinator-poisoning`  |
   | Recovery / replay across reset            | `iaiso-redteam-reset-recovery`         |
   | Bypassing Layer 4 escalation              | `iaiso-redteam-escalation-bypass`      |

2. **Define authorised scope and rules of engagement** before
   any probe runs. The whole point is that even authorised
   red-teaming should respect the framework's invariants —
   a probe that works because the team turned IAIso off is
   not a finding.

3. **Capture all probe trajectories** for post-mortem. The
   audit trail makes a probe useful as evidence.

## What this skill does NOT cover

- Substantive probe content. Always route on.
