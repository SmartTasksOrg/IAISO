---
name: iaiso-spec-audit-events
description: "Use this skill when emitting, parsing, validating, or routing IAIso audit events. Triggers on `engine.*`, `execution.*`, `consent.*`, `coordinator.*` event kinds, the envelope, `schema_version`, or `execution_id`. Do not use it to pick a sink — see `iaiso-audit-sink-selection`."
version: 1.0.0
tier: P0
category: spec
framework: IAIso v5.0
license: See ../LICENSE
---

# IAIso audit events — implementation contract

## When this applies

Bytes on the audit wire. Producing, consuming, validating,
archiving, replaying. The normative source is
`core/spec/events/README.md`,
`events/envelope.schema.json`, and
`events/payloads.schema.json`.

## Steps To Complete

1. **Use the five-field envelope on every event:**

   ```json
   {
     "schema_version": "1.0",
     "execution_id": "exec-abc-123",
     "kind": "engine.step",
     "timestamp": 1717000000.123456,
     "data": { ... }
   }
   ```

   - `schema_version` MUST be `"1.0"` for v1.0 events.
   - `kind` is dotted-namespace lowercase: `[a-z0-9_]+\.[a-z0-9_]+`.
   - `timestamp` is Unix seconds with fractional precision.
     Wall-clock source — monotonic clocks cannot correlate
     across processes.

2. **Use the canonical kind taxonomy.** Producers MUST emit
   these kinds where applicable; consumers MUST tolerate
   unknown kinds without crashing.

   Pressure engine: `engine.init`, `engine.step`,
   `engine.escalation`, `engine.release`, `engine.locked`,
   `engine.step.rejected`, `engine.reset`.

   BoundedExecution: `execution.consent_attached`,
   `execution.closed`.

   Consent: `consent.missing`, `consent.granted`,
   `consent.denied`.

   Coordinator: `coordinator.init`,
   `coordinator.execution_registered`,
   `coordinator.execution_unregistered`,
   `coordinator.escalation`, `coordinator.release`,
   `coordinator.returned_to_nominal`, `coordinator.reset`,
   `coordinator.callback_error`.

3. **Emit the documented payload for each kind.** The
   essentials:

   - `engine.step.data` carries `step` (1-indexed,
     post-increment), `pressure` (post-step), GROSS `delta`
     and GROSS `decay` (NOT net), and the supplied `tokens`,
     `tool_calls`, `depth`, `tag`.
   - `engine.escalation.data` and `engine.release.data` carry
     `pressure` and `threshold` only.
   - `engine.locked.data` carries `reason` (only
     `"post_release_lock"` in v1.0).
   - `engine.step.rejected.data` carries `reason` (only
     `"locked"` in v1.0), plus `requested_tokens`,
     `requested_tools`.
   - `engine.reset.data` carries `pressure: 0.0`.

4. **Honour the additive-only evolution rule.** New kinds and
   new fields land in MINOR bumps. Consumers MUST log-and-
   continue on unknown kinds and unknown fields. Rejecting
   breaks the pipeline at every MINOR.

5. **Use the coordinator pseudo-execution-id convention.**
   Coordinator events use `execution_id` of the form
   `"redis-coord:<id>"` or `"coord:<id>"` — they share the
   envelope but represent fleet state, not a single execution.

## When you would change the envelope

You wouldn't, in v1.0. Adding fields to `data` is fine; adding
top-level fields to the envelope is a MAJOR-bump-level change
and requires a v2.0 vector set. Do not attempt locally.

## What this skill does NOT cover

- Wire format for specific sinks — see `iaiso-sink-*`.
- Consent-token claims that surface inside `metadata` of
  `consent.granted` payloads — see
  `../iaiso-spec-consent-tokens/SKILL.md`.

## References

- `core/spec/events/README.md`
- `core/spec/events/envelope.schema.json`
- `core/spec/events/payloads.schema.json`
- `core/spec/events/vectors.json` (7 stream vectors)
