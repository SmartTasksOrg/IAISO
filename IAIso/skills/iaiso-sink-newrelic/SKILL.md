---
name: iaiso-sink-newrelic
description: "Use this skill when configuring the New Relic audit sink for IAIso events. Triggers on `New Relic`, audit pipeline questions, or alert wiring on top of `iaiso_*` metrics. Do not use this skill to choose a sink — see `iaiso-audit-sink-selection` first."
version: 1.0.0
tier: P2
category: audit-sink
framework: IAIso v5.0
license: See ../LICENSE
---

# New Relic audit sink for IAIso

## When this applies

You have already decided that New Relic is the right destination
(see `iaiso-audit-sink-selection`) and now need to wire it up.

## Steps To Complete

1. **Configure credentials and destination** as documented for
   New Relic. IAIso will not store credentials for you — pass them
   through your normal secrets manager.

2. **Construct the sink** and attach it to the BoundedExecution.

   ```python
   from iaiso.audit.newrelic import NewRelicSink
   ```

3. **Verify the wire format.** Events arrive as Logs with custom attributes. Set `logtype=iaiso` for the parsing rule.

4. **Set up the dropped-event alert.** All IAIso sinks export
   `iaiso_sink_dropped_total{sink="newrelic"}`.
   Page on it being non-zero — silent drops are the single most
   common audit gap.

5. **Validate end-to-end.** Send a synthetic `engine.escalation`
   event through and confirm it lands in New Relic. The first time
   you wire any sink this is a 30-minute exercise that catches
   90% of misconfigurations.

## Payload notes

New Relic Logs has a 1MB-per-payload cap. The sink batches under this limit; very large `metadata` payloads on consent events can approach it.

## What this skill does NOT cover

- Why you might pick New Relic over another sink — see
  `../iaiso-audit-sink-selection/SKILL.md`.
- The audit-event envelope and kinds — see
  `../iaiso-spec-audit-events/SKILL.md`.

## References

- `core/iaiso-python/iaiso/audit/newrelic.py`
- `core/spec/events/README.md`
