---
name: iaiso-compliance-owasp-llm-top-10
description: "Use this skill when mapping IAIso evidence onto OWASP LLM Top 10 requirements. Triggers on OWASP LLM Top 10, audit prep for OWASP LLM Top 10, or specific articles. Do not use it for unrelated regimes — see `iaiso-compliance-router`."
version: 1.0.0
tier: P3
category: compliance
framework: IAIso v5.0
license: See ../LICENSE
---

# IAIso evidence for OWASP LLM Top 10

## When this applies

The deployment is subject to OWASP LLM Top 10 and an auditor / regulator /
certifier needs to see how IAIso satisfies the requirement.

## Steps To Complete

1. **Identify the primary articles / controls.** LLM01 (prompt injection), LLM02 (insecure output), LLM03 (training data poisoning), LLM04 (DoS), LLM06 (sensitive info disclosure), LLM08 (excessive agency), LLM10 (model theft).

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

3. **Focus your evidence pack on:** LLM08 (excessive agency) — IAIso's whole point. ConsentScope is the mechanism; pressure thresholds are the bound.

4. **Use the audit-trail export** for the time window the
   audit covers — see `iaiso-audit-trail-export`.

5. **Document the gaps.** OWASP LLM Top 10 typically has requirements
   IAIso does not address (e.g. data-residency, model-card
   documentation, supplier-due-diligence). Record those as
   complementary controls, not as IAIso failures.

## Gotcha

LLM01 (prompt injection) is partially addressed: even a successful injection cannot exceed the agent's granted scope. The injection itself is not prevented.

## What this skill does NOT cover

- Other regimes — see `../iaiso-compliance-router/SKILL.md`.
- Implementation of IAIso itself — see deployment skills.

## References

- `vision/components/compliance/owasp-llm-top-10/` if shipped
