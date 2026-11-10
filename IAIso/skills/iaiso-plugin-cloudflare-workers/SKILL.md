---
name: iaiso-plugin-cloudflare-workers
description: "Use this skill when deploying an IAIso-governed agent on Cloudflare (Workers). Triggers on `Cloudflare`, `Workers`, or questions about Cloudflare's Layer 0 anchor for IAIso. Do not use this skill for cloud-agnostic deployment — see the `iaiso-deploy-*` family."
version: 1.0.0
tier: P2
category: plugin
framework: IAIso v5.0
license: See ../LICENSE
---

# Cloudflare cloud plugin for IAIso

## When this applies

The agent runs on Cloudflare via Workers and you want IAIso's
Layer 0 hardware/process anchor to derive from Cloudflare's
own quotas rather than a hand-tuned constant.

## Steps To Complete

1. **Install the cloud plugin.**

   ```
   vision/plugins/cloud/workers/
   ```

2. **Choose the Cloudflare resource that anchors Layer 0.** Worker CPU time per request (50ms free, 30s paid). Set IAIso thresholds that the Worker can hit before the platform kills it.
   The IAIso `escalation_threshold` should be computed *from*
   this number — not duplicated next to it.

3. **Wire Workers request handlers** through the plugin's
   wrapper. The wrapper checks pressure before the body
   executes; on `RELEASED` it returns 429 (HTTP) or raises a
   runtime exception (event-driven runtimes).

4. **Forward audit events to Cloudflare's native logging service**
   in addition to (or instead of) a SIEM, if your compliance
   posture requires cloud-native log retention. See
   `iaiso-audit-sink-selection`.

5. **Use Cloudflare secrets management** for HS256 keys and
   coordinator credentials. Never commit these to the agent
   image.

## What this skill does NOT cover

- The system reference design for Cloudflare as a data target —
  see `../iaiso-system-workers/SKILL.md`.
- Generic Helm / Docker / Terraform deployment — see
  `../iaiso-deploy-helm-chart/SKILL.md` and friends.

## References

- `vision/plugins/cloud/workers/`
- `core/iaiso-python/deploy/`
