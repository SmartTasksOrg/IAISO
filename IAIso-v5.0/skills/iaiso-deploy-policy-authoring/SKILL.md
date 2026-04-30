---
name: iaiso-deploy-policy-authoring
description: "Use this skill when writing or reviewing a `policy.yaml` for production. Triggers on policy file authorship, environment promotion, or audit prep. Do not use it to learn the policy schema — see `iaiso-spec-policy-files`."
version: 1.0.0
tier: P1
category: deploy
framework: IAIso v5.0
license: See ../LICENSE
---

# Authoring an IAIso production policy

## When this applies

A policy file is being written for a real environment. This
skill is the operational pattern; the spec contract is in
`iaiso-spec-policy-files`.

## Steps To Complete

1. **Pick the right scope per file.** One policy per
   environment (dev / stage / prod), not one global policy
   with environment switches. The file name encodes the
   environment; the `metadata.environment` field confirms it.

2. **Be explicit even at default values.** Audit reads
   cleanly when the file says what is in effect:

   ```yaml
   version: "1"
   pressure:
     token_coefficient: 0.018      # calibrated 2026-04-15
     tool_coefficient:  0.10
     depth_coefficient: 0.05
     dissipation_per_step:   0.02
     dissipation_per_second: 0.0
     escalation_threshold: 0.85
     release_threshold:    0.95
     post_release_lock:    true
   coordinator:
     aggregator: sum
     escalation_threshold: 5.0
     release_threshold:    8.0
     notify_cooldown_seconds: 1.0
   consent:
     issuer: "iaiso-prod"
     default_ttl_seconds: 1800
     allowed_algorithms: [HS256]
   metadata:
     environment: prod
     owner: platform-team
     calibrated_at: "2026-04-15"
     calibration_run: "swebench-2026q2-3000-trajectories"
   ```

3. **Keep secrets out of the file.** Reference them by name;
   the consent issuer's HS256 key lives in your secrets
   manager (Vault, AWS Secrets Manager, GCP Secret Manager).

4. **Validate before deploying:**

   ```
   iaiso policy validate policies/prod.yaml
   ```

   Errors print a JSON-Pointer-like path to the offending
   field. Fix and re-run.

5. **Version-control the file.** A policy change is a
   deployment-equivalent event — it changes safety
   behaviour. PRs, reviewers, environment promotion,
   rollback. Treat as code.

6. **Promote between environments deliberately.** Dev → stage
   → prod with no auto-promotion. The diff is the audit
   record of "what changed and why".

## What you NEVER do

- Hot-edit a production policy. Reload happens at restart by
  default; your apparent edit may not be live.
- Share consent issuer keys across environments.

## What this skill does NOT cover

- The schema reference — see
  `../iaiso-spec-policy-files/SKILL.md`.
- Coefficient choices — see
  `../iaiso-deploy-calibration/SKILL.md`.

## References

- `core/spec/policy/README.md`
- `core/iaiso-python/iaiso/policy/__main__.py` — template generator
