---
name: iaiso-author-system-template
description: "Use this skill when adding a system to `vision/templates/systems/`. Do not use it to edit existing system READMEs — those follow the system reference-design pattern, not the template pattern."
version: 1.0.0
tier: P3
category: authoring
framework: IAIso v5.0
license: See ../LICENSE
---

# Authoring an IAIso system template

## When this applies

A new external system (CRM, ERP, observability tool) is being
added to the catalogue and needs a reusable prompt template.

## Steps To Complete

1. **Use the six-step template body** from existing templates
   (e.g. `vision/templates/systems/salesforce.template`):
   pressure check → delta calculation → scope verify →
   halt-or-execute → magnification → audit log.

2. **Pick the consent scope namespace** and document the
   `<namespace>.<resource>.<action>` decomposition. List the
   specific actions and which ones are reads vs writes.

3. **Map the system's operations to step inputs.** Document
   which calls are `tool_calls`, what inflates `depth`, and
   any system-specific cost indicator that should drive
   coefficient tuning.

4. **Document the failure mode.** What does the agent return
   when scope is missing? When pressure escalates? When the
   upstream system errors?

5. **Cross-link to the system reference design** under
   `vision/systems/<category>/<system>/`.

## What this skill does NOT cover

- Reference-design narrative — that is `vision/systems/...`,
  not `vision/templates/systems/`.

## References

- `vision/templates/systems/` (existing templates)
