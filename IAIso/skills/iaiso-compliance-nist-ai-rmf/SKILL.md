---
name: iaiso-compliance-nist-ai-rmf
description: "Use this skill when mapping IAIso evidence onto NIST AI RMF 1.0 requirements. Triggers on NIST AI RMF 1.0, audit prep for NIST AI RMF 1.0, or specific articles. Do not use it for unrelated regimes — see `iaiso-compliance-router`."
version: 1.0.0
tier: P3
category: compliance
framework: IAIso v5.0
license: See ../LICENSE
---

# IAIso evidence for NIST AI RMF 1.0

## When this applies

The deployment is subject to NIST AI RMF 1.0 and an auditor / regulator /
certifier needs to see how IAIso satisfies the requirement.

## Steps To Complete

1. **Identify the primary articles / controls.** MAP, MEASURE, MANAGE, GOVERN functions. Particularly MEASURE-2.7 (system tracking), MANAGE-2.3 (incident response), GOVERN-1.2 (oversight processes).

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

3. **Focus your evidence pack on:** MAP and MANAGE — IAIso's pressure model and audit stream provide the continuous measurement and incident-detection backbone.

4. **Use the audit-trail export** for the time window the
   audit covers — see `iaiso-audit-trail-export`.

5. **Document the gaps.** NIST AI RMF 1.0 typically has requirements
   IAIso does not address (e.g. data-residency, model-card
   documentation, supplier-due-diligence). Record those as
   complementary controls, not as IAIso failures.

## Gotcha

NIST RMF is voluntary in the US but referenced by federal procurement; FedRAMP overlap is significant — see `iaiso-compliance-fedramp`.

## What this skill does NOT cover

- Other regimes — see `../iaiso-compliance-router/SKILL.md`.
- Implementation of IAIso itself — see deployment skills.

## References

- `vision/components/compliance/nist-ai-rmf/` if shipped
