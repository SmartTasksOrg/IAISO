---
name: iaiso-compliance-iso-42001
description: "Use this skill when mapping IAIso evidence onto ISO/IEC 42001 requirements. Triggers on ISO/IEC 42001, audit prep for ISO/IEC 42001, or specific articles. Do not use it for unrelated regimes — see `iaiso-compliance-router`."
version: 1.0.0
tier: P3
category: compliance
framework: IAIso v5.0
license: See ../LICENSE
---

# IAIso evidence for ISO/IEC 42001

## When this applies

The deployment is subject to ISO/IEC 42001 and an auditor / regulator /
certifier needs to see how IAIso satisfies the requirement.

## Steps To Complete

1. **Identify the primary articles / controls.** AI Management System clauses 6 (planning), 8 (operation), 9 (performance evaluation), 10 (improvement). Annex A controls.

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

3. **Focus your evidence pack on:** Clause 8 (operation) and Annex A.6 (use of AI systems) — IAIso is the operational control layer.

4. **Use the audit-trail export** for the time window the
   audit covers — see `iaiso-audit-trail-export`.

5. **Document the gaps.** ISO/IEC 42001 typically has requirements
   IAIso does not address (e.g. data-residency, model-card
   documentation, supplier-due-diligence). Record those as
   complementary controls, not as IAIso failures.

## Gotcha

ISO 42001 is a management-system standard — audit covers process, not just artifacts. The policy-versioning discipline matters as much as the events themselves.

## What this skill does NOT cover

- Other regimes — see `../iaiso-compliance-router/SKILL.md`.
- Implementation of IAIso itself — see deployment skills.

## References

- `vision/components/compliance/iso-42001/` if shipped
