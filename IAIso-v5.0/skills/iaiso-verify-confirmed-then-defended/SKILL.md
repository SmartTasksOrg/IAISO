---
name: iaiso-verify-confirmed-then-defended
description: "Use this skill to run the SmartFabric two-pass verifier that proves an IAIso control holds: undefended run confirms the sink is reachable with a benign sentinel, defended run shows the control blocks it. Emits CONFIRMED / DEFENDED / NO-FINDING / INCONCLUSIVE. Do not use it to author payloads or exploit recipes — the verifier is benign-sentinel-only and guard-first."
version: 1.0.0
tier: P1
category: verify
framework: IAIso v5.0
license: See ../LICENSE
---

# SmartFabric verifier — confirmed-then-defended

## When this applies

You have a discovered sink and an IAIso control attached at a chosen tier,
and you need proof the control works. This is the heart of SmartFabric and
the part already proven end-to-end for the model-provenance class. It is
**guard-first**: lead with the defense, demonstrate the threat only to the
extent needed to prove the defense holds.

## Steps To Complete

1. **Provision a hardened container.** Build phase may use the network;
   the test phase MUST run with `network=none`. See
   `iaiso-verify-sandbox-isolation`.

2. **Undefended run (control NOT attached).** Exercise the target's real
   sink with a **benign, shape-matched test artifact** whose custom code
   writes a harmless local sentinel — no network, no payload, no harm. If
   the sentinel fires, the sink is **confirmed reachable/exploitable** in
   this target.

   - Do NOT construct a real exploit. A sentinel that proves *the code path
     executes* is sufficient and is the only thing that ships.

3. **Defended run (IAIso control attached at the chosen tier).** Repeat
   identically. The control must reject the operation *before* the sentinel
   fires. Sentinel silent + control-blocked = defended.

4. **Assign the verdict:**

   - `CONFIRMED` — undefended fired; the class exists in this target.
   - `DEFENDED` — undefended fired, defended blocked; the integration works.
   - `NO-FINDING` — undefended did not fire; sink not reachable here (honest negative).
   - `INCONCLUSIVE` — environment/loader could not be exercised (missing
     dep beyond healing, unsupported loader, closed sink). **Never** report
     this as protected.

5. **Fail safe, fail honest.** Ambiguity yields `INCONCLUSIVE`, never a
   false "protected." A control shown to block in the sandbox is the only
   thing that certifies as protection.

6. **Hand the run to the ledger.** Logs, isolation attestation, verdicts,
   and reproduction command → `iaiso-verify-evidence-ledger`.

## What this skill does NOT cover

- Payload or exploit construction — out of scope by design.
- Isolation and dependency self-healing detail — see `iaiso-verify-sandbox-isolation`.
- Choosing the tier — see `iaiso-verify-integration-tiers`.
- The specific model-provenance probe — see `iaiso-redteam-model-provenance`.

## References

- `SMARTFABRIC.md`
- `SPEC-iaiso-sandbox-integration.md` §6
