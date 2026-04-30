---
name: iaiso-sink-splunk
description: "Use this skill when configuring the Splunk audit sink for IAIso events. Triggers on `Splunk`, audit pipeline questions, or alert wiring on top of `iaiso_*` metrics. Do not use this skill to choose a sink — see `iaiso-audit-sink-selection` first."
version: 1.0.0
tier: P2
category: audit-sink
framework: IAIso v5.0
license: See ../LICENSE
---

# Splunk audit sink for IAIso

## When this applies

You have already decided that Splunk is the right destination
(see `iaiso-audit-sink-selection`) and now need to wire it up.

## Steps To Complete

1. **Configure credentials and destination** as documented for
   Splunk. IAIso will not store credentials for you — pass them
   through your normal secrets manager.

2. **Construct the sink** and attach it to the BoundedExecution.

   ```python
   from iaiso.audit.splunk import SplunkSink
   ```

3. **Verify the wire format.** Events arrive as JSON in the `event` field of HEC requests; `source=iaiso`, `sourcetype=_json`. Set HEC token via env, never in the policy file.

4. **Set up the dropped-event alert.** All IAIso sinks export
   `iaiso_sink_dropped_total{sink="splunk"}`.
   Page on it being non-zero — silent drops are the single most
   common audit gap.

5. **Validate end-to-end.** Send a synthetic `engine.escalation`
   event through and confirm it lands in Splunk. The first time
   you wire any sink this is a 30-minute exercise that catches
   90% of misconfigurations.

## Payload notes

Sends one event per HEC request unless batching is enabled. Set `batch_size=50` and `flush_interval_s=2.0` for typical throughput.

## What this skill does NOT cover

- Why you might pick Splunk over another sink — see
  `../iaiso-audit-sink-selection/SKILL.md`.
- The audit-event envelope and kinds — see
  `../iaiso-spec-audit-events/SKILL.md`.

## References

- `core/iaiso-python/iaiso/audit/splunk.py`
- `core/spec/events/README.md`
