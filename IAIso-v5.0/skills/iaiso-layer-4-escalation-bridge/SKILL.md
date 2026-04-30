---
name: iaiso-layer-4-escalation-bridge
description: "Use this skill when wiring the Layer 4 escalation into your incident pipeline (PagerDuty / OpsGenie / Slack / email). Do not use it for the agent-side escalation behaviour — see `iaiso-runtime-handle-escalation`."
version: 1.0.0
tier: P1
category: layer
framework: IAIso v5.0
license: See ../LICENSE
---

# Wiring the Layer 4 escalation bridge

## When this applies

The deployment has decided escalations need humans in the
loop. This skill is the integration side — how the
`engine.escalation` event reaches the right people.

## Steps To Complete

1. **Choose a pager surface.** PagerDuty, OpsGenie, Slack
   channel with on-call rotation, email + secondary phone
   — pick what your team already responds to. Do not
   invent a new surface for this.

2. **Filter audit events to escalations only.** The
   on-call surface should not see `engine.step`. Subscribe
   a filter (Splunk saved search, Datadog monitor, Loki
   LogQL alert) to `kind="engine.escalation"`.

3. **Render the Layer 4 prompt** verbatim from
   `vision/templates/escalation.template`, with the actual
   pressure value substituted. The prompt is the message
   the human reads; do not paraphrase.

4. **Implement the multi-party authorisation step.** Two
   distinct humans must each grant a fresh ConsentScope.
   The simplest implementation is a Slack form that
   collects two approvals, then posts to the consent
   issuer with the originating `execution_id` bound.

5. **Surface revocation prominently.** If the situation
   resolves before approval (the agent's local pressure
   dissipates), the issued-but-unused token should be
   revoked. The audit trail must show approve → revoke,
   not approve → unused.

6. **Set `notify_cooldown_seconds` thoughtfully.** Default
   1.0 means a noisy execution will page once per second.
   For human-on-call surfaces, raise to 30–60s and rely on
   the audit stream for fine-grained signal.

## What this skill does NOT cover

- Agent-side escalation behaviour — see
  `../iaiso-runtime-handle-escalation/SKILL.md`.
- Issuing the consent token — see
  `../iaiso-deploy-consent-issuance/SKILL.md`.

## References

- `vision/templates/escalation.template`
- `core/spec/events/README.md` §3.1 (`engine.escalation`)
