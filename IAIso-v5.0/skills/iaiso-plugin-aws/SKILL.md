---
name: iaiso-plugin-aws
description: "Use this skill when deploying an IAIso-governed agent on AWS (Lambda / Fargate / EC2). Triggers on `AWS`, `Lambda / Fargate / EC2`, or questions about AWS's Layer 0 anchor for IAIso. Do not use this skill for cloud-agnostic deployment — see the `iaiso-deploy-*` family."
version: 1.0.0
tier: P2
category: plugin
framework: IAIso v5.0
license: See ../LICENSE
---

# AWS cloud plugin for IAIso

## When this applies

The agent runs on AWS via Lambda / Fargate / EC2 and you want IAIso's
Layer 0 hardware/process anchor to derive from AWS's
own quotas rather than a hand-tuned constant.

## Steps To Complete

1. **Install the cloud plugin.**

   ```
   vision/plugins/cloud/aws/
   ```

2. **Choose the AWS resource that anchors Layer 0.** Lambda function timeout for short-lived agents; ECS task quota for long-lived; EC2 vCPU limit for self-hosted.
   The IAIso `escalation_threshold` should be computed *from*
   this number — not duplicated next to it.

3. **Wire Lambda / Fargate / EC2 request handlers** through the plugin's
   wrapper. The wrapper checks pressure before the body
   executes; on `RELEASED` it returns 429 (HTTP) or raises a
   runtime exception (event-driven runtimes).

4. **Forward audit events to AWS's native logging service**
   in addition to (or instead of) a SIEM, if your compliance
   posture requires cloud-native log retention. See
   `iaiso-audit-sink-selection`.

5. **Use AWS secrets management** for HS256 keys and
   coordinator credentials. Never commit these to the agent
   image.

## What this skill does NOT cover

- The system reference design for AWS as a data target —
  see `../iaiso-system-aws/SKILL.md`.
- Generic Helm / Docker / Terraform deployment — see
  `../iaiso-deploy-helm-chart/SKILL.md` and friends.

## References

- `vision/plugins/cloud/aws/`
- `core/iaiso-python/deploy/`
