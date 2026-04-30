---
name: iaiso-spec-router
description: "Use this skill when a question is about IAIso wire formats — JWT claims, audit envelope, policy YAML, Redis keys, pressure math, conformance vectors. Routes to the contract skill for the right subsystem. Do not use it as the answer; always route on."
version: 1.0.0
tier: P0
category: spec
framework: IAIso v5.0
license: See ../LICENSE
---

# IAIso spec router

## When this applies

The request involves bytes on the wire — a JWT, an audit JSON,
a policy file, a Redis hash entry, a pressure number, a
conformance vector. This skill routes to the normative contract
skill; deeper questions belong there.

## Steps To Complete

1. **Identify the artefact** in the request and load the
   matching contract skill:

   | Artefact                                          | Skill                                |
   |---------------------------------------------------|--------------------------------------|
   | a number representing pressure or a coefficient   | `iaiso-spec-pressure-model`          |
   | a JWT (3 dot-separated base64 segments)           | `iaiso-spec-consent-tokens`          |
   | a JSON object with `schema_version`, `kind`, `data` | `iaiso-spec-audit-events`          |
   | a YAML/JSON file with `version: "1"` at the top   | `iaiso-spec-policy-files`            |
   | a Redis key starting with `iaiso:coord:`          | `iaiso-spec-coordinator-protocol`    |
   | a vectors.json file or test failure under `core/spec/` | `iaiso-spec-conformance-vectors` |

2. **If the request spans subsystems** (e.g. "how does an audit
   event reference a consent scope"), load both — events
   reference scopes by `jti` and execution by `execution_id`,
   and that crosses two contracts.

3. **If the request is asking which subsystem owns a field**:

   | Field                       | Owner subsystem |
   |-----------------------------|-----------------|
   | `escalation_threshold`      | pressure        |
   | `release_threshold`         | pressure        |
   | `iss`/`sub`/`scopes`/`jti`  | consent         |
   | `schema_version`            | events          |
   | `coordinator.aggregator`    | policy + coordinator |
   | the Lua script              | coordinator     |
   | `1e-9` tolerance            | pressure (cited globally) |

4. **If the request is "is this conformant"**, route to
   `iaiso-spec-conformance-vectors` — it covers running the
   vector suite, not the individual contract.

5. **Do not paraphrase the contracts here.** This skill knows
   *which* contract; the contracts know *what* it says.

## What this skill does NOT cover

- Substantive answers about any wire format. Always route on.

## References

- `core/spec/README.md` — the spec hub
- `core/spec/VERSION` — current spec version
