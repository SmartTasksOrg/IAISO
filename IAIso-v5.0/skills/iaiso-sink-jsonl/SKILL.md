---
name: iaiso-sink-jsonl
description: "Use this skill when configuring the JSONL local file audit sink for IAIso events. Triggers on `JSONL local file`, audit pipeline questions, or alert wiring on top of `iaiso_*` metrics. Do not use this skill to choose a sink — see `iaiso-audit-sink-selection` first."
version: 1.0.0
tier: P2
category: audit-sink
framework: IAIso v5.0
license: See ../LICENSE
---

# JSONL local file audit sink for IAIso

## When this applies

You have already decided that JSONL local file is the right destination
(see `iaiso-audit-sink-selection`) and now need to wire it up.

## Steps To Complete

1. **Configure credentials and destination** as documented for
   JSONL local file. IAIso will not store credentials for you — pass them
   through your normal secrets manager.

2. **Construct the sink** and attach it to the BoundedExecution.

   ```python
   from iaiso.audit.jsonl import JSONLlocalfileSink
   ```

3. **Verify the wire format.** Newline-delimited JSON envelopes. Rotates by size. `fsync` per line is the safest default.

4. **Set up the dropped-event alert.** All IAIso sinks export
   `iaiso_sink_dropped_total{sink="jsonl"}`.
   Page on it being non-zero — silent drops are the single most
   common audit gap.

5. **Validate end-to-end.** Send a synthetic `engine.escalation`
   event through and confirm it lands in JSONL local file. The first time
   you wire any sink this is a 30-minute exercise that catches
   90% of misconfigurations.

## Payload notes

Pair with Fluent Bit / Vector for at-least-once delivery. See `iaiso-audit-jsonl-with-shipper`.

## What this skill does NOT cover

- Why you might pick JSONL local file over another sink — see
  `../iaiso-audit-sink-selection/SKILL.md`.
- The audit-event envelope and kinds — see
  `../iaiso-spec-audit-events/SKILL.md`.

## References

- `core/iaiso-python/iaiso/audit/jsonl.py`
- `core/spec/events/README.md`
