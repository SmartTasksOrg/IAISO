---
name: iaiso-sink-sumologic
description: "Use this skill when configuring the Sumo Logic audit sink for IAIso events. Triggers on `Sumo Logic`, audit pipeline questions, or alert wiring on top of `iaiso_*` metrics. Do not use this skill to choose a sink — see `iaiso-audit-sink-selection` first."
version: 1.0.0
tier: P2
category: audit-sink
framework: IAIso v5.0
license: See ../LICENSE
---

# Sumo Logic audit sink for IAIso

## When this applies

You have already decided that Sumo Logic is the right destination
(see `iaiso-audit-sink-selection`) and now need to wire it up.

## Steps To Complete

1. **Configure credentials and destination** as documented for
   Sumo Logic. IAIso will not store credentials for you — pass them
   through your normal secrets manager.

2. **Construct the sink** and attach it to the BoundedExecution.

   ```python
   from iaiso.audit.sumologic import SumoLogicSink
   ```

3. **Verify the wire format.** Events arrive as JSON to the HTTP source. Set `sourceCategory=iaiso` in Sumo so dashboards filter cleanly.

4. **Set up the dropped-event alert.** All IAIso sinks export
   `iaiso_sink_dropped_total{sink="sumologic"}`.
   Page on it being non-zero — silent drops are the single most
   common audit gap.

5. **Validate end-to-end.** Send a synthetic `engine.escalation`
   event through and confirm it lands in Sumo Logic. The first time
   you wire any sink this is a 30-minute exercise that catches
   90% of misconfigurations.

## Payload notes

HTTP source endpoint must be created in Sumo first; the URL is the credential — guard it.

## What this skill does NOT cover

- Why you might pick Sumo Logic over another sink — see
  `../iaiso-audit-sink-selection/SKILL.md`.
- The audit-event envelope and kinds — see
  `../iaiso-spec-audit-events/SKILL.md`.

## References

- `core/iaiso-python/iaiso/audit/sumologic.py`
- `core/spec/events/README.md`
