---
name: iaiso-audit-sink-selection
description: "Use this skill when picking an audit sink for a deployment. Triggers on \"where do events go\", \"stdout vs SIEM\", \"drop vs block\". Do not use it to configure a specific sink — load the matching `iaiso-sink-*` skill once chosen."
version: 1.0.0
tier: P1
category: audit
framework: IAIso v5.0
license: See ../LICENSE
---

# Choosing an IAIso audit sink

## When this applies

A new deployment, or an existing one outgrowing its current
sink. The decision is shaped by durability needs, regulatory
posture, and existing infrastructure.

## Steps To Complete

1. **Clarify durability requirement.** Two posture options:

   - **Best-effort** (default): webhook sinks use bounded
     queues; dropped events surface on
     `iaiso_sink_dropped_total`. Dev / internal / non-
     regulated workloads.
   - **At-least-once**: write to a local JSONL file on a
     durable volume, ship with Fluent Bit / Vector to your
     archive. Regulated workloads where every event must
     reach storage.

2. **Use the trade-off table to pick a sink:**

   | Sink           | Use when                                                  | Don't use for           |
   |----------------|-----------------------------------------------------------|-------------------------|
   | `stdout`       | Dev loop only.                                            | Anything in prod.       |
   | `JSONL`        | Regulated / at-least-once. Pair with shipper.             | Tiny dev runs.          |
   | `Splunk`       | Existing Splunk SIEM, HEC available.                      | No Splunk infra.        |
   | `Datadog`      | Existing Datadog, logs-to-metrics already in flow.        | High-cardinality fields.|
   | `Elastic`      | Existing ECS-based pipeline.                              | Non-ECS schema needs.   |
   | `Loki`         | Existing Grafana/Loki, label-disciplined ops.             | High label cardinality. |
   | `Sumo Logic`   | Existing Sumo, HTTP source pre-provisioned.               | No Sumo infra.          |
   | `New Relic`    | Existing NR Logs, custom-attribute consumer.              | Non-NR pipelines.       |
   | `Webhook`      | Custom destination not on the list.                       | Where retries are mandatory and your endpoint can't dedup.|

3. **Set up the dropped-events alert.** Every webhook-style
   sink ships `iaiso_sink_dropped_total`. Page on non-zero —
   a non-zero count for >1 minute is an audit gap.

4. **For at-least-once delivery: subclass `WebhookSink`** to
   block on queue-full instead of dropping. This trades
   availability for durability — choose deliberately.

5. **For regulated workloads: prefer JSONL + shipper.** The
   agent's audit emission decouples from SIEM uptime; the
   shipper handles retries and back-pressure. See
   `iaiso-audit-jsonl-with-shipper`.

## What you NEVER do

- Run prod with the stdout sink. Audit data goes to terminal
  buffers and is lost on container restart.
- Daisy-chain agent → webhook → another webhook → SIEM.
  Every hop is a place to drop. Land in storage at the first
  hop or in the second at most.

## What this skill does NOT cover

- Per-sink wire format and configuration — see
  `iaiso-sink-*` for each.

## References

- `core/iaiso-python/iaiso/audit/`
- `known-limitations.md` — audit-delivery architecture
