---
name: iaiso-spec-policy-files
description: "Use this skill when authoring, validating, or migrating an IAIso policy YAML/JSON file. Triggers on `version: \"1\"`, the `pressure:`/`coordinator:`/`consent:`/`metadata:` sections, or `iaiso policy validate`. Do not use it to pick coefficients — see `iaiso-deploy-calibration`."
version: 1.0.0
tier: P0
category: spec
framework: IAIso v5.0
license: See ../LICENSE
---

# IAIso policy files — implementation contract

## When this applies

A policy.yaml or policy.json is being written, validated, or
migrated. The normative source is `core/spec/policy/README.md`
and `policy/policy.schema.json`.

## Steps To Complete

1. **Use the documented top-level shape.** A policy file is a
   JSON object (YAML accepted as a JSON superset, no anchors,
   no merge keys). The `version` key is REQUIRED and MUST be
   `"1"` for this spec version.

   ```yaml
   version: "1"
   pressure:    { ... }
   coordinator: { ... }
   consent:     { ... }
   metadata:    { ... }
   ```

   Unknown top-level keys produce a warning, never a failure
   — that is how forward compatibility works.

2. **Set every pressure field that matters for your
   deployment, even at default.** Audit reads cleanly when the
   file is explicit:

   ```yaml
   pressure:
     token_coefficient:    0.015
     tool_coefficient:     0.08
     depth_coefficient:    0.05
     dissipation_per_step: 0.02
     dissipation_per_second: 0.0
     escalation_threshold: 0.85
     release_threshold:    0.95
     post_release_lock:    true
   ```

   Cross-field rule: `release_threshold > escalation_threshold`.
   Both in `[0, 1]`. The loader MUST raise on violation.

3. **Set coordinator thresholds by aggregator choice.**
   Defaults (5.0 / 8.0) are calibrated for `sum`. For `mean` a
   sensible range is `[0, 1]`. For `max` typically `[0, 1]`.
   Loaders MAY warn on inconsistency; they MUST NOT fail.

   ```yaml
   coordinator:
     aggregator: sum            # sum | mean | max | weighted_sum
     escalation_threshold: 5.0
     release_threshold:    8.0
     notify_cooldown_seconds: 1.0
     weights:        { exec-vip: 2.0 }   # weighted_sum only
     default_weight: 1.0                  # weighted_sum only
   ```

4. **Set consent fields when issuing tokens from this
   deployment.** `required_scopes` is advisory — it does not
   enforce that issued tokens contain those scopes; that is the
   app's job.

   ```yaml
   consent:
     issuer: "my-org"
     default_ttl_seconds:  3600
     required_scopes:      [tools.read]
     allowed_algorithms:   [HS256, RS256]
   ```

5. **Stamp environment metadata.** `metadata` is preserved but
   not interpreted. Use it for `environment`, `owner`, cost-
   allocation tags, anything you want to read back from a
   compliance archive.

6. **Validate before deploying.** Run
   `iaiso policy validate path/to/policy.yaml` (or `python -m
   iaiso policy validate`). Errors include a JSON-Pointer-like
   path so you can find the offending field.

## Common mistakes

- Forgetting `version: "1"`. The loader rejects.
- Setting `release_threshold = escalation_threshold`. Must be
  strict inequality.
- Storing secrets in `metadata`. The whole policy file is
  typically read-many — secrets belong in a secrets manager
  and are referenced by name, not value.

## What this skill does NOT cover

- Picking the numbers — see
  `../iaiso-deploy-calibration/SKILL.md` and
  `../iaiso-deploy-threshold-tuning/SKILL.md`.

## References

- `core/spec/policy/README.md` (normative)
- `core/spec/policy/policy.schema.json`
- `core/spec/policy/vectors.json` (17 vectors)
