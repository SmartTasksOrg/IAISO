---
name: iaiso-compliance-fedramp
description: "Use this skill when mapping IAIso evidence onto FedRAMP requirements. Triggers on FedRAMP, audit prep for FedRAMP, or specific articles. Do not use it for unrelated regimes — see `iaiso-compliance-router`."
version: 1.0.0
tier: P3
category: compliance
framework: IAIso v5.0
license: See ../LICENSE
---

# IAIso evidence for FedRAMP

## When this applies

The deployment is subject to FedRAMP and an auditor / regulator /
certifier needs to see how IAIso satisfies the requirement.

## Steps To Complete

1. **Identify the primary articles / controls.** Moderate baseline NIST 800-53 controls — particularly AU (audit and accountability), AC (access control), CA (assessment), SI (system integrity).

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

3. **Focus your evidence pack on:** AU-2 (event types), AU-3 (content), AU-6 (review) — the IAIso audit envelope was designed against this control family.

4. **Use the audit-trail export** for the time window the
   audit covers — see `iaiso-audit-trail-export`.

5. **Document the gaps.** FedRAMP typically has requirements
   IAIso does not address (e.g. data-residency, model-card
   documentation, supplier-due-diligence). Record those as
   complementary controls, not as IAIso failures.

## Gotcha

FedRAMP requires monthly continuous monitoring reports. Pressure-trajectory and escalation-rate metrics are the natural feed.

## What this skill does NOT cover

- Other regimes — see `../iaiso-compliance-router/SKILL.md`.
- Implementation of IAIso itself — see deployment skills.

## References

- `vision/components/compliance/fedramp/` if shipped
