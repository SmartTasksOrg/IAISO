---
name: iaiso-deploy-terraform
description: "Use this skill when provisioning IAIso infra via Terraform. Triggers on Terraform module, Redis provisioning, IAM policy for SIEM sinks. Do not use it for application-level config — see `iaiso-deploy-policy-authoring`."
version: 1.0.0
tier: P1
category: deploy
framework: IAIso v5.0
license: See ../LICENSE
---

# Provisioning IAIso infra with Terraform

## When this applies

A new environment is being stood up, or an existing one is
being IaC-ified. The shipped module is in
`core/iaiso-python/deploy/terraform/`.

## Steps To Complete

1. **Use the shipped module.** It provisions:

   - the Redis instance for the coordinator,
   - the secrets-manager entries for HS256 / RS256 keys,
   - IAM policy / role for the agent to read those secrets,
   - IAM policy / API key for the chosen audit sink
     (HEC token for Splunk, API key for Datadog, etc.),
   - DNS / LB rules if the agent fronts an HTTP API.

2. **Pin the module version.** Same reasoning as pinning
   `iaiso==0.2.0` in the container — Terraform module
   versions move.

3. **Stamp resources with environment tags** matching your
   policy file's `metadata.environment`. This is what
   links Terraform state to audit records.

4. **Use separate workspaces per environment.** Dev / stage
   / prod do not share state. Promotion is `terraform plan
   -var-file=prod.tfvars` against the prod workspace, not a
   branch in dev.

5. **Plan and review every change.** Like the policy file,
   infra changes are deployment-equivalent — they affect
   safety behaviour. PR + reviewer + audit trail.

## What this skill does NOT cover

- Helm — see `../iaiso-deploy-helm-chart/SKILL.md`.
- Cloud-specific anchors — see
  `../iaiso-layer-0-hardware-anchor/SKILL.md`.

## References

- `core/iaiso-python/deploy/terraform/`
