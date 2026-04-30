---
name: iaiso-sink-webhook
description: "Use this skill when configuring the Generic webhook audit sink for IAIso events. Triggers on `Generic webhook`, audit pipeline questions, or alert wiring on top of `iaiso_*` metrics. Do not use this skill to choose a sink — see `iaiso-audit-sink-selection` first."
version: 1.0.0
tier: P2
category: audit-sink
framework: IAIso v5.0
license: See ../LICENSE
---

# Generic webhook audit sink for IAIso

## When this applies

You have already decided that Generic webhook is the right destination
(see `iaiso-audit-sink-selection`) and now need to wire it up.

## Steps To Complete

1. **Configure credentials and destination** as documented for
   Generic webhook. IAIso will not store credentials for you — pass them
   through your normal secrets manager.

2. **Construct the sink** and attach it to the BoundedExecution.

   ```python
   from iaiso.audit.webhook import GenericwebhookSink
   ```

3. **Verify the wire format.** POSTs JSON envelopes to a configured URL. Authenticate with a header (`Authorization: Bearer ...`) — basic auth is supported but discouraged.

4. **Set up the dropped-event alert.** All IAIso sinks export
   `iaiso_sink_dropped_total{sink="webhook"}`.
   Page on it being non-zero — silent drops are the single most
   common audit gap.

5. **Validate end-to-end.** Send a synthetic `engine.escalation`
   event through and confirm it lands in Generic webhook. The first time
   you wire any sink this is a 30-minute exercise that catches
   90% of misconfigurations.

## Payload notes

The default sink for everything not on the list. Bounded queue; drop on full surfaces as `iaiso_sink_dropped_total`.

## What this skill does NOT cover

- Why you might pick Generic webhook over another sink — see
  `../iaiso-audit-sink-selection/SKILL.md`.
- The audit-event envelope and kinds — see
  `../iaiso-spec-audit-events/SKILL.md`.

## References

- `core/iaiso-python/iaiso/audit/webhook.py`
- `core/spec/events/README.md`
