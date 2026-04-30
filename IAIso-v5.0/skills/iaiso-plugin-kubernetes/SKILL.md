---
name: iaiso-plugin-kubernetes
description: "Use this skill when deploying an IAIso-governed agent on Kubernetes (any cluster). Triggers on `Kubernetes`, `any cluster`, or questions about Kubernetes's Layer 0 anchor for IAIso. Do not use this skill for cloud-agnostic deployment — see the `iaiso-deploy-*` family."
version: 1.0.0
tier: P2
category: plugin
framework: IAIso v5.0
license: See ../LICENSE
---

# Kubernetes cloud plugin for IAIso

## When this applies

The agent runs on Kubernetes via any cluster and you want IAIso's
Layer 0 hardware/process anchor to derive from Kubernetes's
own quotas rather than a hand-tuned constant.

## Steps To Complete

1. **Install the cloud plugin.**

   ```
   vision/plugins/cloud/kubernetes/
   ```

2. **Choose the Kubernetes resource that anchors Layer 0.** Pod CPU/memory requests. Layer 0 anchor here is the resource limit, not the cloud provider quota directly.
   The IAIso `escalation_threshold` should be computed *from*
   this number — not duplicated next to it.

3. **Wire any cluster request handlers** through the plugin's
   wrapper. The wrapper checks pressure before the body
   executes; on `RELEASED` it returns 429 (HTTP) or raises a
   runtime exception (event-driven runtimes).

4. **Forward audit events to Kubernetes's native logging service**
   in addition to (or instead of) a SIEM, if your compliance
   posture requires cloud-native log retention. See
   `iaiso-audit-sink-selection`.

5. **Use Kubernetes secrets management** for HS256 keys and
   coordinator credentials. Never commit these to the agent
   image.

## What this skill does NOT cover

- The system reference design for Kubernetes as a data target —
  see `../iaiso-system-kubernetes/SKILL.md`.
- Generic Helm / Docker / Terraform deployment — see
  `../iaiso-deploy-helm-chart/SKILL.md` and friends.

## References

- `vision/plugins/cloud/kubernetes/`
- `core/iaiso-python/deploy/`
