---
name: iaiso-deploy-enforcement-mode
description: "Use this skill when choosing or reviewing `enforcement_mode` for a deployment, when a policy file needs a strict/permissive decision, or when someone asks why an engine refused to construct with a StrictModeError. Do not use it for tuning thresholds or coefficients — load `iaiso-deploy-threshold-tuning` or `iaiso-deploy-calibration` instead."
version: 1.0.0
tier: P0
category: deploy
framework: IAIso v5.0
license: See ../LICENSE
---

# Choosing enforcement_mode

## When this applies

A deployment is being configured, or reviewed, and someone needs to decide
whether IAIso should fail closed at boot. Also applies when an engine raises
`StrictModeError` and the reason is unclear.

Introduced in spec 1.1. Available in Python, Node, and Go only.

## Steps To Complete

1. **Default to `strict` for anything that leaves a laptop.** Under `strict`
   the engine refuses to construct, naming the failing condition, when any of
   these hold:

   | Condition | Why it is fatal |
   |---|---|
   | Consent algorithm is HS256 with an auto-generated key | Nothing outside the process can verify what it signed |
   | The only audit sink is `NullSink` — or none was passed | Escalations would be unobservable |
   | `post_release_lock` is `false` | A released execution resumes immediately |
   | Coefficients are library defaults and no `calibration_artifact` is named | Thresholds will never fire, or fire constantly |

   ```python
   from iaiso import BoundedExecution, PressureConfig, StrictModeError
   from iaiso.audit import JsonlFileSink

   try:
       ex = BoundedExecution.start(
           config=PressureConfig(token_coefficient=0.011),
           audit_sink=JsonlFileSink("audit.jsonl"),
           enforcement_mode="strict",
           calibration_artifact="calibration/2026-07-01.json",
       )
   except StrictModeError as exc:
       # The message names the condition. Fix the condition; do not
       # downgrade to permissive to make the error go away.
       raise
   ```

2. **Use `permissive` only in tests and exploration.** It is the default for
   backward compatibility. Each condition warns once per process through
   `logging.getLogger("iaiso")` (Python), `setWarnLogger` (Node), or
   `core.WarnLogger` (Go), then execution proceeds.

3. **Never treat an unknown mode as permissive.** The SDKs raise on an
   unrecognised value rather than downgrading. If you are porting IAIso, keep
   that behaviour — a silent downgrade is how an operator ends up believing a
   deployment is strict when it is not.

4. **Verify the guard actually fires before you trust it.** The published PyPI
   wheel may predate this feature; the version string alone will not tell you.

   ```bash
   python -c "import iaiso; print(hasattr(iaiso, 'StrictModeError'))"
   ```

   If that prints `False`, `enforcement_mode="strict"` is being silently ignored.
   Install from a checkout.

5. **Check that the calibration artifact is real.** The guard checks only that
   `calibration_artifact` is a non-empty string. It does not open the file or
   compare its coefficients to the config. `calibration_artifact="yes"` passes.
   When reviewing a deployment, open the named file yourself and confirm the
   coefficients match.

## Common mistakes

- Catching `StrictModeError` and retrying in permissive. That converts a
  refusal into a warning nobody reads.
- Setting `strict` on a port that does not implement it. Rust, PHP, Java, C#,
  Swift, and Ruby are at spec 1.0: they accept a strict policy and construct a
  degraded engine anyway.
- Assuming `strict` provides containment. It does not. See `iaiso-mental-model`.

## What this skill does NOT cover

- Deriving coefficients — see `iaiso-deploy-calibration`.
- Threshold values — see `iaiso-deploy-threshold-tuning`.
- The policy file format — see `iaiso-spec-policy-files`.
- Spend caps — see `iaiso-runtime-cost-governance`.

## References

- `core/iaiso-python/iaiso/core/engine.py`
- `core/spec/policy/policy.schema.json`
- `LIMITATIONS.md`
