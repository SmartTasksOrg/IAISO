---
name: iaiso-sink-datadog
description: "Use this skill when configuring the Datadog audit sink for IAIso events. Triggers on `Datadog`, audit pipeline questions, or alert wiring on top of `iaiso_*` metrics. Do not use this skill to choose a sink — see `iaiso-audit-sink-selection` first."
version: 1.0.0
tier: P2
category: audit-sink
framework: IAIso v5.0
license: See ../LICENSE
---

# Datadog audit sink for IAIso

## When this applies

You have already decided that Datadog is the right destination
(see `iaiso-audit-sink-selection`) and now need to wire it up.

## Steps To Complete

1. **Configure credentials and destination** as documented for
   Datadog. IAIso will not store credentials for you — pass them
   through your normal secrets manager.

2. **Construct the sink** and attach it to the BoundedExecution.

   ```python
   from iaiso.audit.datadog import DatadogSink
   ```

3. **Verify the wire format.** Events arrive as Datadog Logs with `service=iaiso`, `source=iaiso-events`. Use the API key, not the application key.

4. **Set up the dropped-event alert.** All IAIso sinks export
   `iaiso_sink_dropped_total{sink="datadog"}`.
   Page on it being non-zero — silent drops are the single most
   common audit gap.

5. **Validate end-to-end.** Send a synthetic `engine.escalation`
   event through and confirm it lands in Datadog. The first time
   you wire any sink this is a 30-minute exercise that catches
   90% of misconfigurations.

## Payload notes

High-cardinality fields (execution_id) become tags. Strip them or you will hit Datadog's tag-cardinality cap and get throttled.

## What this skill does NOT cover

- Why you might pick Datadog over another sink — see
  `../iaiso-audit-sink-selection/SKILL.md`.
- The audit-event envelope and kinds — see
  `../iaiso-spec-audit-events/SKILL.md`.

## References

- `core/iaiso-python/iaiso/audit/datadog.py`
- `core/spec/events/README.md`
