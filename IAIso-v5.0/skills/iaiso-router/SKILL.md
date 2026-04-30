---
name: iaiso-router
description: "Use this skill whenever a request mentions IAIso, pressure, consent scope, escalation, audit event, solution pack, or governed agent — this is the master dispatch that points to the right deeper skill. Do not use it as the answer itself; always route on to a more specific skill."
version: 1.0.0
tier: P0
category: routing
framework: IAIso v5.0
license: See ../LICENSE
---

# IAIso master router

## When this applies

Anything IAIso-related. This skill is a one-page index — it
decides which deeper skill the agent should load next. It does
not answer questions itself; if it tries to, that is a bug.

## Steps To Complete

1. **Identify the request category** by matching keywords:

   | Keyword in the request                                        | Load this skill                              |
   |---------------------------------------------------------------|----------------------------------------------|
   | "pressure", "threshold", "step", "delta", coefficient names   | `iaiso-spec-pressure-model`                  |
   | "consent token", "JWT", "scope", "iss", "jti", HS256, RS256   | `iaiso-spec-consent-tokens`                  |
   | "audit event", "kind", "envelope", "execution_id", `engine.*` | `iaiso-spec-audit-events`                    |
   | "policy.yaml", "policy.json", "version: 1"                    | `iaiso-spec-policy-files`                    |
   | "Redis", "coordinator", fleet pressure, Lua                   | `iaiso-spec-coordinator-protocol`            |
   | "conformance", "67 vectors", `vectors.json`                   | `iaiso-spec-conformance-vectors`             |
   | wrapping an agent, `BoundedExecution`, governed runtime       | `iaiso-runtime-governed-agent`               |
   | "escalation", Layer 4, multi-party auth                       | `iaiso-runtime-handle-escalation`            |
   | scope check before action                                     | `iaiso-runtime-consent-scope-check`          |
   | "release", state wipe, atomic reset                           | `iaiso-runtime-atomic-reset`                 |
   | back-prop magnification, output refinement                    | `iaiso-runtime-back-prop-magnification`      |
   | calibration, picking coefficients                             | `iaiso-deploy-calibration`                   |
   | LangChain / CrewAI / AutoGen / etc.                           | matching `iaiso-integ-*`                     |
   | Anthropic / OpenAI / Gemini / Bedrock / Mistral / Cohere      | matching `iaiso-llm-*`                       |
   | Splunk / Datadog / Loki / Elastic / etc.                      | matching `iaiso-sink-*`                      |
   | EU AI Act / NIST / ISO / SOC2 / GDPR / HIPAA / FedRAMP        | matching `iaiso-compliance-*`                |
   | "red team", probe, bypass attempt                             | `iaiso-redteam-router`                       |
   | "port to <language>"                                          | `iaiso-port-new-language`                    |
   | "pressure went up", "consent denied", "fleet wrong"           | matching `iaiso-diagnose-*`                  |

2. **If the request is conceptual** ("what is IAIso", "what is
   pressure", "what are the layers"), load
   `iaiso-mental-model` first — do not try to explain from
   memory of these tables.

3. **If the request is about a wire format**, route through
   `iaiso-spec-router` rather than guessing at the right
   contract skill.

4. **If the request is about an integration**, route through
   `iaiso-integ-router` (orchestrators), `iaiso-audit-router`
   (compliance), or `iaiso-redteam-router` (adversarial).

5. **If you cannot localise the request to one skill in two
   hops**, ask the user a clarifying question rather than
   loading several skills speculatively.

## What this skill does NOT cover

- Anything substantive. This is dispatch only.

## References

- `INDEX.md` for the full skill catalogue
- `CONVENTIONS.md` for skill anatomy
