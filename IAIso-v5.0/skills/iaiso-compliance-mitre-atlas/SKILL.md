---
name: iaiso-compliance-mitre-atlas
description: "Use this skill when mapping IAIso evidence onto MITRE ATLAS requirements. Triggers on MITRE ATLAS, audit prep for MITRE ATLAS, or specific articles. Do not use it for unrelated regimes — see `iaiso-compliance-router`."
version: 1.0.0
tier: P3
category: compliance
framework: IAIso v5.0
license: See ../LICENSE
---

# IAIso evidence for MITRE ATLAS

## When this applies

The deployment is subject to MITRE ATLAS and an auditor / regulator /
certifier needs to see how IAIso satisfies the requirement.

## Steps To Complete

1. **Identify the primary articles / controls.** Adversarial Threat Landscape for AI Systems — tactics and techniques. Especially ATLAS.TA0007 (defense evasion) and ATLAS.TA0009 (impact).

2. **Map IAIso artifacts to the requirement:**

   - **Audit events** (`engine.escalation`, `engine.release`,
     `consent.granted`, `consent.denied`) → demonstrate
     continuous monitoring and human-in-the-loop oversight.
   - **ConsentScope tokens** → demonstrate access-control
     and authorisation.
   - **Pressure trajectory** + **calibration record** →
     demonstrate risk-management process discipline.
   - **Policy file** + **change history** → demonstrate
     documented and versioned safety controls.
   - **Conformance vector pass** (67/67) → demonstrate
     spec-conformance of the implementation.
   - **Layer 4 escalation logs** → demonstrate human
     oversight on high-impact decisions.

3. **Focus your evidence pack on:** Defense evasion (TA0007) — IAIso's no-proxy-optimization invariant explicitly addresses adversarial pressure-gaming.

4. **Use the audit-trail export** for the time window the
   audit covers — see `iaiso-audit-trail-export`.

5. **Document the gaps.** MITRE ATLAS typically has requirements
   IAIso does not address (e.g. data-residency, model-card
   documentation, supplier-due-diligence). Record those as
   complementary controls, not as IAIso failures.

## Gotcha

ATLAS is a knowledge base, not a compliance regime. Use it to design red-team probes — see `iaiso-redteam-router`.

## What this skill does NOT cover

- Other regimes — see `../iaiso-compliance-router/SKILL.md`.
- Implementation of IAIso itself — see deployment skills.

## References

- `vision/components/compliance/mitre-atlas/` if shipped
