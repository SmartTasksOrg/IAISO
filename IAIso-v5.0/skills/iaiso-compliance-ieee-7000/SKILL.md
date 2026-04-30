---
name: iaiso-compliance-ieee-7000
description: "Use this skill when mapping IAIso evidence onto IEEE 7000-2021 requirements. Triggers on IEEE 7000-2021, audit prep for IEEE 7000-2021, or specific articles. Do not use it for unrelated regimes — see `iaiso-compliance-router`."
version: 1.0.0
tier: P3
category: compliance
framework: IAIso v5.0
license: See ../LICENSE
---

# IAIso evidence for IEEE 7000-2021

## When this applies

The deployment is subject to IEEE 7000-2021 and an auditor / regulator /
certifier needs to see how IAIso satisfies the requirement.

## Steps To Complete

1. **Identify the primary articles / controls.** Value-based engineering, ethical considerations during system design. Particularly stakeholder elicitation and value-prioritisation processes.

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

3. **Focus your evidence pack on:** IEEE 7000's value-prioritisation lifecycle ↔ IAIso's calibration record + policy review process.

4. **Use the audit-trail export** for the time window the
   audit covers — see `iaiso-audit-trail-export`.

5. **Document the gaps.** IEEE 7000-2021 typically has requirements
   IAIso does not address (e.g. data-residency, model-card
   documentation, supplier-due-diligence). Record those as
   complementary controls, not as IAIso failures.

## Gotcha

IEEE 7000 is a process standard, not a technical one. Evidence is meeting minutes, value lists, and traceability matrices — not just audit events.

## What this skill does NOT cover

- Other regimes — see `../iaiso-compliance-router/SKILL.md`.
- Implementation of IAIso itself — see deployment skills.

## References

- `vision/components/compliance/ieee-7000/` if shipped
