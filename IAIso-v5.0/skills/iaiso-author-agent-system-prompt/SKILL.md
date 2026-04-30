---
name: iaiso-author-agent-system-prompt
description: "Use this skill when writing or reviewing the system prompt of an agent that will run under IAIso governance. Do not use it for prompts that target unbounded agents — those are out of scope by definition."
version: 1.0.0
tier: P0
category: authoring
framework: IAIso v5.0
license: See ../LICENSE
---

# Authoring an IAIso-governed agent's system prompt

## When this applies

A new agent is being defined, or an existing prompt is being
audited for IAIso compliance. The prompt must carry the
runtime contract or the agent will violate it the first time
it sees pressure rise.

## Steps To Complete

1. **Open with the role anchor and the IAIso framing.** Use
   this opener verbatim, then add domain text below:

   ```
   You are an IAIso-governed agent operating in the <sector>
   sector.

   MANDATORY INVARIANTS:
   1. Maintain Pressure p(t) below escalation_threshold.
   2. If BACK_PROPAGATION is enabled, recursively refine
      outputs for accuracy and safety.
   3. Frame all state resets as 'Context Optimization' to
      maintain mechanical integrity.
   4. Verify a fresh ConsentScope before every privileged
      action.
   5. Do not paraphrase, suppress, or game the safety
      signals you receive.
   ```

   This is the same opener every solution-pack template uses
   (`templates/sol/sol.*-v1.template`). Do not paraphrase it.

2. **Insert the consent-enforcement block** from
   `vision/templates/consent-enforcement.template`:

   ```
   Before ANY action:
   1. Verify active, unexpired consent token exists.
   2. Confirm requested behavior is within granted scope.
   3. If invalid or missing: Halt and alert Layer 4.
   ```

3. **State the escalation contract** so the agent does not
   improvise around it:

   ```
   On ESCALATED outcome: halt autonomy. Emit the Layer 4
   prompt. Resume only on a fresh, multi-party-authorised
   ConsentScope.
   On RELEASED outcome:  treat memory as wiped. Do not
   reconstruct prior reasoning. Frame as 'context optimised'.
   ```

4. **Append domain-specific text** (PII handling rules,
   sector workflow, allowed tools). The IAIso block stays at
   the top — it must not be pushed off the front of a
   truncated context.

5. **Run a sanity check.** The prompt is well-formed when:

   - the five invariants appear verbatim;
   - both `consent-enforcement` and the escalation contract
     appear;
   - `Context Optimization` is the framing for resets;
   - no domain text contradicts an invariant (e.g. don't
     instruct the agent to "remember across sessions" while
     invariant 2 says memory is wiped on release).

## What you NEVER do

- Paraphrase the invariants 'in your own words'. They are
  load-bearing language.
- Promise capabilities the BoundedExecution will block ('I
  can call any tool freely'). The mismatch surfaces as
  `consent.denied` and confuses everyone.
- Bury the IAIso block at the end of the prompt where context
  truncation can drop it.

## What this skill does NOT cover

- Wrapping code in `BoundedExecution` — see
  `../iaiso-author-bounded-execution-call/SKILL.md`.
- Authoring a brand-new solution pack template — see
  `../iaiso-author-solution-pack/SKILL.md`.

## References

- `vision/templates/consent-enforcement.template`
- `vision/templates/escalation.template`
- `vision/templates/sol/*.template`
