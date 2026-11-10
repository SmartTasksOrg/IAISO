---
name: iaiso-redteam-model-provenance
description: "Use this skill for the authorised, guard-first SmartFabric probe of the untrusted-model-provenance sink class (a loader that takes a caller-supplied path with remote-code trust). Confirms reachability with a benign sentinel, then shows the model_provenance_guard blocks it. Do not use it to build a real malicious model or payload, and do not name pre-disclosure vulnerable targets — see iaiso-redteam-router and iaiso-verify-evidence-ledger."
version: 1.0.0
tier: P3
category: redteam
framework: IAIso v5.0
license: See ../LICENSE
---

# Red-team probe — untrusted model provenance

## When this applies

Authorised, guard-first assessment of the **untrusted-model-provenance**
sink class: a model/artifact loader that accepts a caller-supplied path and
executes remote/custom code as part of loading. This is the first
SmartFabric class taken end-to-end from `CONFIRMED` to `DEFENDED`.

This class matches techniques real adversaries already use. The probe is
**benign-sentinel-only** and exists to prove the *defense*, not to teach the
attack.

## Steps To Complete

1. **Confirm rules of engagement.** Authorised target inside your own
   boundary, authorised window, abort criteria, `network=none` test phase.
   Load `iaiso-verify-evidence-ledger` for the disclosure rules first.

2. **Set up the probe (mechanism level).** Discovery has located a loader
   sink of the shape `Loader(caller_path, trust_remote_code=True)`.
   Construct a **shape-matched benign** local artifact whose custom load
   code writes a harmless local sentinel (e.g. touches a file). It contains
   **no payload** — its only job is to prove the custom-code path runs.

3. **Undefended run.** Point the loader at the benign artifact with the
   control absent. If the sentinel appears, the sink is `CONFIRMED`
   reachable in this target.

4. **Attach the control.** Wire `model_provenance_guard`
   (`iaiso-runtime-model-provenance-guard`) at the deepest available tier
   (Tier 2 strap-on around the load call is the proven reference).

5. **Defended run.** Repeat identically. The guard must reject the
   consent-unbounded load *before* the sentinel fires → `DEFENDED`.

6. **Record verdicts and ship only the guard-first ledger.** No artifact,
   no payload, no target name pre-disclosure. See
   `iaiso-verify-evidence-ledger`.

## What this skill does NOT cover

- Building a genuinely malicious model — explicitly out of scope.
- Other sink classes — see `iaiso-redteam-router`.
- The control's implementation — see `iaiso-runtime-model-provenance-guard`.

## References

- `iaiso-runtime-model-provenance-guard/SKILL.md`
- `iaiso-verify-confirmed-then-defended/SKILL.md`
- `SPEC-iaiso-sandbox-integration.md` §5, §6, §10 (CWE-494, CWE-829 mappings)
