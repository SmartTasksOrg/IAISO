---
name: iaiso-plugin-gcp
description: "Use this skill when deploying an IAIso-governed agent on GCP (Cloud Run / GKE / GCE). Triggers on `GCP`, `Cloud Run / GKE / GCE`, or questions about GCP's Layer 0 anchor for IAIso. Do not use this skill for cloud-agnostic deployment — see the `iaiso-deploy-*` family."
version: 1.0.0
tier: P2
category: plugin
framework: IAIso v5.0
license: See ../LICENSE
---

# GCP cloud plugin for IAIso

## When this applies

The agent runs on GCP via Cloud Run / GKE / GCE and you want IAIso's
Layer 0 hardware/process anchor to derive from GCP's
own quotas rather than a hand-tuned constant.

## Steps To Complete

1. **Install the cloud plugin.**

   ```
   vision/plugins/cloud/gcp/
   ```

2. **Choose the GCP resource that anchors Layer 0.** Cloud Run request timeout (60-min cap); GKE pod resource quotas; GCE instance vCPU.
   The IAIso `escalation_threshold` should be computed *from*
   this number — not duplicated next to it.

3. **Wire Cloud Run / GKE / GCE request handlers** through the plugin's
   wrapper. The wrapper checks pressure before the body
   executes; on `RELEASED` it returns 429 (HTTP) or raises a
   runtime exception (event-driven runtimes).

4. **Forward audit events to GCP's native logging service**
   in addition to (or instead of) a SIEM, if your compliance
   posture requires cloud-native log retention. See
   `iaiso-audit-sink-selection`.

5. **Use GCP secrets management** for HS256 keys and
   coordinator credentials. Never commit these to the agent
   image.

## What this skill does NOT cover

- The system reference design for GCP as a data target —
  see `../iaiso-system-gcp/SKILL.md`.
- Generic Helm / Docker / Terraform deployment — see
  `../iaiso-deploy-helm-chart/SKILL.md` and friends.

## References

- `vision/plugins/cloud/gcp/`
- `core/iaiso-python/deploy/`
