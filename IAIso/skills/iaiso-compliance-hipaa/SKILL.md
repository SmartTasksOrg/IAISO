---
name: iaiso-compliance-hipaa
description: "Use this skill when mapping IAIso evidence onto HIPAA requirements. Triggers on HIPAA, audit prep for HIPAA, or specific articles. Do not use it for unrelated regimes — see `iaiso-compliance-router`."
version: 1.0.0
tier: P3
category: compliance
framework: IAIso v5.0
license: See ../LICENSE
---

# IAIso evidence for HIPAA

## When this applies

The deployment is subject to HIPAA and an auditor / regulator /
certifier needs to see how IAIso satisfies the requirement.

## Steps To Complete

1. **Identify the primary articles / controls.** Security Rule §164.312 (technical safeguards) — access control, audit controls, integrity. Privacy Rule §164.502 (uses and disclosures of PHI).

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

3. **Focus your evidence pack on:** Audit controls (§164.312(b)) — the IAIso audit stream IS the control. Access control (§164.312(a)) — ConsentScope tokens.

4. **Use the audit-trail export** for the time window the
   audit covers — see `iaiso-audit-trail-export`.

5. **Document the gaps.** HIPAA typically has requirements
   IAIso does not address (e.g. data-residency, model-card
   documentation, supplier-due-diligence). Record those as
   complementary controls, not as IAIso failures.

## Gotcha

PHI must not appear in audit metadata. Use opaque execution_id binding to your record system; investigators with the right authority can join from there.

## What this skill does NOT cover

- Other regimes — see `../iaiso-compliance-router/SKILL.md`.
- Implementation of IAIso itself — see deployment skills.

## References

- `vision/components/compliance/hipaa/` if shipped
