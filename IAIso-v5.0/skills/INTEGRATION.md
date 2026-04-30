# Integrating IAIso skills into a system

Three integration paths, in order of friction.

## Path 1 — Drop-in for Claude / Anthropic Skills

If you are using Claude or another Skills-aware client, the entire
`skills/` directory drops in next to existing skills. The client's
own discovery picks them up — name, description, body — and the
skills become loadable by `iaiso-*` name.

No changes required beyond placing the directory.

## Path 2 — System-prompt injection from your own agent code

For agents not running on a Skills-aware client, load the
relevant skill body and inject it into the system prompt at the
moment it becomes relevant.

```python
from skills.loader.loader import SkillRegistry

registry = SkillRegistry.load("./skills")

system_prompt = "\n\n".join([
    base_role_block,
    registry["iaiso-author-agent-system-prompt"].body,
    registry["iaiso-runtime-governed-agent"].body,
])
```

The router skills (`iaiso-router`, `iaiso-spec-router`,
`iaiso-compliance-router`, `iaiso-redteam-router`) are designed
to be loaded eagerly so the agent can dispatch to deeper skills
on demand.

## Path 3 — Programmatic registry

For agent frameworks that run multi-skill dispatch themselves
(LangChain SkillRouter, custom orchestrators), use the registry:

```python
from skills.loader.loader import SkillRegistry

registry = SkillRegistry.load("./skills")

# By tier
for skill in registry.tier("P0"):
    runtime.register(skill.name, skill.body)

# By category
for skill in registry.category("compliance"):
    audit_runtime.register(skill.name, skill.body)
```

```typescript
import { SkillRegistry } from "./skills/loader/loader";
const registry = await SkillRegistry.load("./skills");
for (const s of registry.tier("P0")) {
  runtime.register(s.name, s.body);
}
```

## What the loader gives you

A `Skill` value with: `name`, `description`, `version`, `tier`,
`category`, `framework`, `license`, and `body` (the markdown
content after the frontmatter). Plus parsed `metadata` from any
extra frontmatter fields you add downstream.

## Recommended loading patterns

- **Eager load** the routers: the agent should always have
  `iaiso-router`, `iaiso-spec-router`, and the matching
  area router available.
- **Lazy load** integration / system / sink skills: only when
  the relevant system enters the conversation.
- **Always load** `iaiso-runtime-governed-agent` for any
  agent running inside a BoundedExecution. It is the conduct
  contract and is not optional.

## Versioning

The frontmatter `version:` is per-skill semver. Bump on:

- non-trivial body change → patch;
- new `## Steps To Complete` step → minor;
- changed step semantics or removed steps → major.

The frontmatter `framework: IAIso v5.0` binds the catalogue to a
spec version. When the spec bumps to v6, the catalogue re-binds —
that is a coordinated change, not a per-skill bump.
