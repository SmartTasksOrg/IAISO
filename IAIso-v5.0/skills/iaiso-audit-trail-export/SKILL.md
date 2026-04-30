---
name: iaiso-audit-trail-export
description: "Use this skill when exporting an audit trail for a compliance package or incident investigation. Triggers on evidence pack assembly, time-windowed export, regulatory submission. Do not use it to choose a sink — see `iaiso-audit-sink-selection`."
version: 1.0.0
tier: P3
category: audit
framework: IAIso v5.0
license: See ../LICENSE
---

# Exporting IAIso audit trails

## When this applies

Compliance audit, incident investigation, or regulatory
submission needs a packaged, immutable audit trail for a
specific time window.

## Steps To Complete

1. **Define the window.** UTC, inclusive start, exclusive
   end. Document the timezone explicitly.

2. **Pull from the durable archive, not the live sink.**
   If you JSONL+shipper, that is your archive. If you SIEM
   directly, the SIEM's export is the source.

3. **Filter to the relevant `execution_id` set.** Most
   investigations are per-execution; a quarterly compliance
   export is broader. Document the filter.

4. **Verify completeness.** For each `execution_id`,
   confirm you have the full envelope sequence:
   `engine.init` → ... → `execution.closed`. A truncated
   trail is a finding.

5. **Hash the export.** SHA-256 the file; record the hash
   in a separate manifest signed by the investigator. This
   is chain of custody.

6. **Bundle with policy file and calibration record.** The
   audit trail alone does not tell the auditor what the
   thresholds were — bundle the policy file in effect during
   the window.

## What this skill does NOT cover

- Investigating WHAT a trail shows — see
  `../iaiso-audit-incident-investigation/SKILL.md`.

## References

- `core/iaiso-python/iaiso/audit/export.py` if shipped
