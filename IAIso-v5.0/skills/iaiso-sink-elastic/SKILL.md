---
name: iaiso-sink-elastic
description: "Use this skill when configuring the Elastic / OpenSearch audit sink for IAIso events. Triggers on `Elastic / OpenSearch`, audit pipeline questions, or alert wiring on top of `iaiso_*` metrics. Do not use this skill to choose a sink — see `iaiso-audit-sink-selection` first."
version: 1.0.0
tier: P2
category: audit-sink
framework: IAIso v5.0
license: See ../LICENSE
---

# Elastic / OpenSearch audit sink for IAIso

## When this applies

You have already decided that Elastic / OpenSearch is the right destination
(see `iaiso-audit-sink-selection`) and now need to wire it up.

## Steps To Complete

1. **Configure credentials and destination** as documented for
   Elastic / OpenSearch. IAIso will not store credentials for you — pass them
   through your normal secrets manager.

2. **Construct the sink** and attach it to the BoundedExecution.

   ```python
   from iaiso.audit.elastic import Elastic/OpenSearchSink
   ```

3. **Verify the wire format.** Documents conform to ECS conventions where the IAIso envelope maps cleanly. Provide an index template that maps `data.pressure` as `float` so you can graph it.

4. **Set up the dropped-event alert.** All IAIso sinks export
   `iaiso_sink_dropped_total{sink="elastic"}`.
   Page on it being non-zero — silent drops are the single most
   common audit gap.

5. **Validate end-to-end.** Send a synthetic `engine.escalation`
   event through and confirm it lands in Elastic / OpenSearch. The first time
   you wire any sink this is a 30-minute exercise that catches
   90% of misconfigurations.

## Payload notes

Index name should rotate (daily): `iaiso-events-YYYY.MM.DD`. The sink writes via the bulk API; configure ILM to roll the alias.

## What this skill does NOT cover

- Why you might pick Elastic / OpenSearch over another sink — see
  `../iaiso-audit-sink-selection/SKILL.md`.
- The audit-event envelope and kinds — see
  `../iaiso-spec-audit-events/SKILL.md`.

## References

- `core/iaiso-python/iaiso/audit/elastic.py`
- `core/spec/events/README.md`
