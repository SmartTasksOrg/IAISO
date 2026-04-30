---
name: iaiso-plugin-azure
description: "Use this skill when deploying an IAIso-governed agent on Azure (Functions / Container Apps / VMs). Triggers on `Azure`, `Functions / Container Apps / VMs`, or questions about Azure's Layer 0 anchor for IAIso. Do not use this skill for cloud-agnostic deployment — see the `iaiso-deploy-*` family."
version: 1.0.0
tier: P2
category: plugin
framework: IAIso v5.0
license: See ../LICENSE
---

# Azure cloud plugin for IAIso

## When this applies

The agent runs on Azure via Functions / Container Apps / VMs and you want IAIso's
Layer 0 hardware/process anchor to derive from Azure's
own quotas rather than a hand-tuned constant.

## Steps To Complete

1. **Install the cloud plugin.**

   ```
   vision/plugins/cloud/azure/
   ```

2. **Choose the Azure resource that anchors Layer 0.** Functions timeout (Premium plan extends to 60min); Container Apps scaling rules; VM vCPU.
   The IAIso `escalation_threshold` should be computed *from*
   this number — not duplicated next to it.

3. **Wire Functions / Container Apps / VMs request handlers** through the plugin's
   wrapper. The wrapper checks pressure before the body
   executes; on `RELEASED` it returns 429 (HTTP) or raises a
   runtime exception (event-driven runtimes).

4. **Forward audit events to Azure's native logging service**
   in addition to (or instead of) a SIEM, if your compliance
   posture requires cloud-native log retention. See
   `iaiso-audit-sink-selection`.

5. **Use Azure secrets management** for HS256 keys and
   coordinator credentials. Never commit these to the agent
   image.

## What this skill does NOT cover

- The system reference design for Azure as a data target —
  see `../iaiso-system-azure/SKILL.md`.
- Generic Helm / Docker / Terraform deployment — see
  `../iaiso-deploy-helm-chart/SKILL.md` and friends.

## References

- `vision/plugins/cloud/azure/`
- `core/iaiso-python/deploy/`
