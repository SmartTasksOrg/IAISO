---
name: iaiso-compliance-eu-ai-act
description: "Use this skill when mapping IAIso evidence onto the EU AI Act requirements. Triggers on the EU AI Act, audit prep for the EU AI Act, or specific articles. Do not use it for unrelated regimes — see `iaiso-compliance-router`."
version: 1.0.0
tier: P3
category: compliance
framework: IAIso v5.0
license: See ../LICENSE
---

# IAIso evidence for the EU AI Act

## When this applies

The deployment is subject to the EU AI Act and an auditor / regulator /
certifier needs to see how IAIso satisfies the requirement.

## Steps To Complete

1. **Identify the primary articles / controls.** High-risk-system articles 9 (risk management), 10 (data and data governance), 12 (record-keeping), 14 (human oversight), 15 (accuracy, robustness, cybersecurity).

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

3. **Focus your evidence pack on:** Article 14 (human oversight) — IAIso's Layer 4 escalation is a direct mechanical implementation. Article 12 (record-keeping) — audit events are the records.

4. **Use the audit-trail export** for the time window the
   audit covers — see `iaiso-audit-trail-export`.

5. **Document the gaps.** the EU AI Act typically has requirements
   IAIso does not address (e.g. data-residency, model-card
   documentation, supplier-due-diligence). Record those as
   complementary controls, not as IAIso failures.

## Gotcha

The Act distinguishes high-risk systems from general-purpose AI; IAIso applies cleanly to deployment-stage agents (high-risk category). It does not address foundation-model training obligations (Article 53).

## What this skill does NOT cover

- Other regimes — see `../iaiso-compliance-router/SKILL.md`.
- Implementation of IAIso itself — see deployment skills.

## References

- `vision/components/compliance/eu-ai-act/` if shipped
