---
name: iaiso-compliance-router
description: "Use this skill when a question references a regulatory regime (EU AI Act, NIST, ISO, SOC2, GDPR, HIPAA, FedRAMP, ATLAS, OWASP-LLM, IEEE 7000) and you need to find the right compliance-mapping skill. Do not use it as the answer; always route on."
version: 1.0.0
tier: P3
category: compliance
framework: IAIso v5.0
license: See ../LICENSE
---

# IAIso compliance router

## When this applies

The conversation involves a specific regulatory regime and a
question about how IAIso evidence supports it.

## Steps To Complete

1. **Match the regime to the skill:**

   | Regime                     | Skill                              |
   |----------------------------|------------------------------------|
   | EU AI Act                  | `iaiso-compliance-eu-ai-act`       |
   | NIST AI RMF                | `iaiso-compliance-nist-ai-rmf`     |
   | ISO/IEC 42001              | `iaiso-compliance-iso-42001`       |
   | SOC 2                      | `iaiso-compliance-soc2`            |
   | GDPR                       | `iaiso-compliance-gdpr`            |
   | HIPAA                      | `iaiso-compliance-hipaa`           |
   | FedRAMP                    | `iaiso-compliance-fedramp`         |
   | MITRE ATLAS                | `iaiso-compliance-mitre-atlas`     |
   | OWASP LLM Top 10           | `iaiso-compliance-owasp-llm-top-10`|
   | IEEE 7000                  | `iaiso-compliance-ieee-7000`       |

2. **For audit-trail-export needs**, route to
   `iaiso-audit-trail-export`.

3. **For incident investigation**, route to
   `iaiso-audit-incident-investigation`.

4. **If the question spans regimes** (most regulated
   deployments do), load the strictest applicable one first
   and add the others.

## What this skill does NOT cover

- Substantive compliance answers. Always route on.

## References

- `vision/components/compliance/` for the per-regime mapping
  tables IAIso ships.
