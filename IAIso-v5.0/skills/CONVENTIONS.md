# Skill anatomy and conventions

## File layout

Each skill lives in its own directory, named by the skill name:

```
skills/<skill-name>/SKILL.md
```

## Naming

- Lowercase kebab-case.
- Always prefixed `iaiso-`.
- Sub-prefixed by area:
  - `iaiso-spec-*` — wire-format contracts
  - `iaiso-runtime-*` — agent conduct
  - `iaiso-author-*` — content authoring
  - `iaiso-deploy-*` — deployment / config
  - `iaiso-audit-*` — audit-related
  - `iaiso-layer-N-*` — layer-specific
  - `iaiso-integ-*` — orchestrator integration
  - `iaiso-llm-*` — LLM provider middleware
  - `iaiso-sink-*` — audit-sink wiring
  - `iaiso-system-*` — system reference design
  - `iaiso-plugin-*` — cloud / platform plugin
  - `iaiso-compliance-*` — regulatory mapping
  - `iaiso-redteam-*` — adversarial probe
  - `iaiso-port-*` — language porting
  - `iaiso-diagnose-*` — diagnostic procedure

## Frontmatter

Every SKILL.md opens with a YAML frontmatter block:

```yaml
---
name: iaiso-spec-pressure-model
description: "Use this skill when ... Do not use it for ..."
version: 1.0.0
tier: P0
category: spec
framework: IAIso v5.0
license: See ../LICENSE
---
```

Required fields: `name`, `description`, `version`, `tier`,
`category`, `framework`, `license`.

The `description` is single-line, ≤ ~1000 characters, and contains
both a "use when" and a "do not use" clause. This is what an
LLM scans during dispatch.

## Body structure

```markdown
# <Title>

## When this applies

<one paragraph on the trigger conditions>

## Steps To Complete

1. <action 1, with code where appropriate>
2. <action 2>
...

## What this skill does NOT cover

- <pointer to sibling skill 1>
- <pointer to sibling skill 2>

## References

- <path/to/spec or doc>
```

The exact section headings are not required, but every skill has:

- a `## Steps To Complete` section (load-bearing for evalite-style
  skill harnesses);
- explicit out-of-scope pointers so the agent routes on rather
  than answering speculatively.

## Length

Skills are focused. Most are 50–150 lines. Routers are shorter.
Spec contracts are the longest (the contract is the content).
Wrappers are short (delegation lives in the linked deeper skill).

## Cross-references

Use relative paths from the skill's own folder:

```markdown
See `../iaiso-runtime-governed-agent/SKILL.md`.
```

This makes the catalogue work both as filesystem-loaded skills
(Claude) and as a git-readable doc tree.
