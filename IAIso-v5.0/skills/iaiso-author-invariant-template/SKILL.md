---
name: iaiso-author-invariant-template
description: "Use this skill when authoring an invariant template (`vision/templates/inv-1.template` and friends). Do not use it for the five core IAIso invariants — those are spec, not authored content."
version: 1.0.0
tier: P3
category: authoring
framework: IAIso v5.0
license: See ../LICENSE
---

# Authoring an invariant template

## When this applies

A deployment is adding domain-specific invariants on top of
the five core ones. These appear as numbered invariants
(`inv-2`, `inv-3`...) layered into the system prompt below
the IAIso block.

## Steps To Complete

1. **Number it after the five core invariants.** The core
   five are inviolable; domain invariants are additions, not
   replacements.

2. **Phrase it as a constraint, not a goal.** "Do not <X>",
   "Always <Y> before <Z>". Goals get optimised against;
   constraints get respected.

3. **Include the violation behaviour.** Which event kind to
   emit (use a custom kind under your namespace, e.g.
   `mycorp.inv.violated`), what scope is required to
   continue.

4. **Test it adversarially.** A red-team probe should be able
   to violate the invariant under stress; if not, the
   invariant is too vague to bind behaviour. See
   `iaiso-redteam-router`.

5. **Version-control the template** alongside policy. An
   invariant change is a deployment-equivalent event.

## What this skill does NOT cover

- The five core invariants — see
  `../iaiso-mental-model/SKILL.md`.

## References

- `vision/templates/inv-1.template`
