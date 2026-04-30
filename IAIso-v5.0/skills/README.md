# IAIso Skills

This directory holds the **Claude Skills catalogue** for IAIso v5.0 —
~140 focused, single-purpose skill files that an LLM agent loads on
demand to act correctly inside the framework.

## What's here

```
skills/
├── README.md           — this file
├── INDEX.md            — full catalogue, grouped by tier and category
├── CONVENTIONS.md      — anatomy of a SKILL.md, frontmatter spec
├── INTEGRATION.md      — how to consume from Claude or programmatically
├── loader/
│   ├── loader.py       — Python loader / registry
│   └── loader.ts       — TypeScript loader / registry
└── <skill-name>/
    └── SKILL.md        — one folder per skill
```

## Where this lives in the IAIso repo

This directory belongs at the **top level** of the IAIso v5.0 repo,
alongside `core/` (the shipping SDK) and `vision/` (the design
vision and reference designs):

```
IAIso-v5.0/
├── core/              — normative spec + 9 language SDKs
├── vision/            — vision / reference designs / templates
├── skills/            — THIS directory
├── README.md
├── LICENSE
└── ...
```

The skills reference paths into both `core/` and `vision/`. They
are designed to be authoritative for "how an agent should act
inside IAIso", with `core/spec/` winning on any wire-format
question and `vision/templates/` winning on prompt content.

## Quick start

### Drop-in for Claude

If you are using Claude or another Anthropic Skills-aware client,
copy the entire directory next to your other skills. Each
`<skill-name>/SKILL.md` is loaded the same way as any Anthropic
public skill (`/mnt/skills/...` style).

### Programmatic loading from agent code

```python
from skills.loader.loader import SkillRegistry

registry = SkillRegistry.load("./skills")

# Look up a skill by name
skill = registry["iaiso-runtime-governed-agent"]
print(skill.description)
print(skill.body)        # markdown body, ready for system-prompt injection

# Filter by tier or category
for s in registry.tier("P0"):
    print(s.name)
```

```typescript
import { SkillRegistry } from "./skills/loader/loader";
const registry = await SkillRegistry.load("./skills");
const skill = registry.get("iaiso-runtime-governed-agent");
```

## Tier model

- **P0 — Required.** Foundation, spec contracts, runtime conduct,
  authoring patterns. Without these, an IAIso agent cannot
  function.
- **P1 — Production deployment.** Calibration, audit, identity,
  coordinator, layer-specific deployment, deployment artifacts.
- **P2 — Integration wrappers.** Per-orchestrator,
  per-LLM-provider, per-sink, per-cloud, per-system, per-platform.
  Thin, focused, often delegates to a P0/P1 skill.
- **P3 — Specialised.** Authoring new templates, compliance
  evidence packs, red-team probes, language porting, diagnostics.

See `INDEX.md` for the full list.

## Versioning

Each skill carries `version:` in its frontmatter. The catalogue as
a whole follows the IAIso v5.0 spec — frontmatter `framework:
IAIso v5.0` declares the binding. When the spec bumps, the
relevant skills bump.

## License

See `../LICENSE` at the top of the IAIso repo.
