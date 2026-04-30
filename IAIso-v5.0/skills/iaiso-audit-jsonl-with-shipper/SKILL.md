---
name: iaiso-audit-jsonl-with-shipper
description: "Use this skill for regulated environments where every audit event must reach durable storage. Triggers on JSONL sink, Fluent Bit, Vector, at-least-once delivery, audit retention. Do not use it for dev or low-stakes deployments — best-effort sinks are simpler."
version: 1.0.0
tier: P1
category: audit
framework: IAIso v5.0
license: See ../LICENSE
---

# JSONL sink with a downstream shipper

## When this applies

Compliance regime requires every event to reach durable
storage. A direct webhook to a SIEM cannot guarantee that
under SIEM downtime — a local file plus a shipper can.

## Steps To Complete

1. **Configure `JSONLSink` to a durable mount.** The path
   must survive pod restarts:

   ```python
   from iaiso.audit import JSONLSink
   sink = JSONLSink(
       path="/var/log/iaiso/events.jsonl",
       rotate_at_bytes=128 * 1024 * 1024,  # 128 MiB
   )
   ```

   Use a Kubernetes PVC or an EC2 EBS volume. Local ephemeral
   disk defeats the durability guarantee.

2. **Set up rotation and fsync discipline.** The reference
   sink rotates by size; pair with logrotate or your
   platform's equivalent. fsync per-line is the safest
   default; per-block is a perf trade-off you take
   deliberately.

3. **Deploy a shipper sidecar.** Either:

   - **Fluent Bit** with a `tail` input on the file, parsed
     as JSON, output to your archive.
   - **Vector** with a `file` source, `remap` transform if
     your archive expects a different envelope, sink to
     the destination.

   Either way, the shipper keeps a position file so a crash
   does not lose progress.

4. **Hash for chain-of-custody if regulated.** SHA-256 each
   rotated file before the shipper picks it up; record the
   hash in a separate manifest. Auditors will ask.

5. **Set retention to match policy.** SOC 2 / ISO 27001 /
   HIPAA all imply retention windows. The shipper writes to
   cold storage; lifecycle rules expire after the window.
   Do not rely on the agent host for retention.

6. **Test failure recovery.** Kill the shipper for an hour;
   confirm events do not drop and the shipper catches up
   cleanly when restarted. This is the test that justifies
   the architecture.

## What this skill does NOT cover

- Sink choice in general — see
  `../iaiso-audit-sink-selection/SKILL.md`.
- Compliance evidence pack — see `iaiso-compliance-*`.

## References

- `core/iaiso-python/iaiso/audit/jsonl.py`
- Fluent Bit / Vector documentation (external)
