---
name: iaiso-author-prompt-contract
description: "Use this skill when documenting the formal contract a prompt holds the agent to — beyond the IAIso block. Do not use it for ad-hoc prompt authoring; this is for regulated deployments where the prompt itself is an auditable artifact."
version: 1.0.0
tier: P3
category: authoring
framework: IAIso v5.0
license: See ../LICENSE
---

# Authoring a prompt contract

## When this applies

The deployment is regulated such that the agent's prompt
becomes an audited document — what the agent is and is not
promising to do, in writing, signed by reviewers.

## Steps To Complete

1. **State the agent's role and authority bound** in the
   opening, after the IAIso invariant block. "Authorised to
   read X, write Y, escalate Z. Not authorised to <list>."

2. **List allowed tools by name** and the scope each
   requires. The list is closed; tools not on it must
   trigger consent failure.

3. **State the user contract.** What the user can ask for,
   what the agent will refuse, what triggers escalation.

4. **Include a versioning footer.** Prompt version, signed
   reviewers, calibration date. The audit-trail-export
   script picks this up.

5. **Run a contract conformance check.** The prompt is
   conformant if: every allowed tool has a scope; every
   refusal class is enumerated; every escalation trigger
   maps to an `engine.escalation` source condition.

## What this skill does NOT cover

- General system-prompt authoring — see
  `../iaiso-author-agent-system-prompt/SKILL.md`.

## References

- `vision/templates/sol/*.template` as worked examples
