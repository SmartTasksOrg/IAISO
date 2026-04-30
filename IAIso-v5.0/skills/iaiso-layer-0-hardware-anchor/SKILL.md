---
name: iaiso-layer-0-hardware-anchor
description: "Use this skill when configuring Layer 0 anchors — BIOS / hypervisor / hardware kill switches that bound IAIso from below. Triggers on Intel / AMD / NVIDIA / ARM reference designs, FLOP caps, attestation. Do not use it for in-process containment — that is Layer 1+."
version: 1.0.0
tier: P1
category: layer
framework: IAIso v5.0
license: See ../LICENSE
---

# Configuring Layer 0 hardware anchors

## When this applies

The deployment requires a containment guarantee below the
Python / JVM / Node process — i.e. process compromise must
not bypass IAIso. This is Layer 0.

## Steps To Complete

1. **Pick the anchor type that matches your platform.** The
   reference designs:

   - **Intel**: SGX enclaves for HS256 keys, RDT for compute
     caps. See `vision/systems/hardware/intel/`.
   - **AMD**: SEV for VM-level isolation, MCA for compute
     tracking. See `vision/systems/hardware/amd/`.
   - **NVIDIA**: MIG partitions as compute caps for GPU
     workloads. See `vision/systems/hardware/nvidia/`.
   - **ARM**: TrustZone for key storage. See
     `vision/systems/hardware/arm/`.

   Cloud-managed platforms expose these via Nitro
   (AWS), Confidential Computing (Azure), Confidential VMs
   (GCP).

2. **Derive `escalation_threshold` from the hardware quota,
   don't duplicate it.** If the platform caps your VM at
   1e13 FLOPs/s, the IAIso threshold is `0.85 ×
   hardware_cap` rather than `0.85` next to a hand-set
   1e13 in Python.

3. **Stand up attestation.** A Layer 0 anchor is only
   trustworthy if it is attested. Use the platform's
   attestation API (Intel SGX quote, AMD SEV report) to
   prove the anchor is the right hardware before issuing
   consent tokens against it.

4. **Wire the kill switch.** When the platform releases (FLOP
   quota exhausted, enclave panic), the IAIso runtime should
   observe a hard signal and emit `engine.locked` with the
   Layer 0 reason. Do not retry; do not silently degrade.

5. **Document the chain in your audit metadata.** "Layer 0
   anchor: AWS Nitro / Intel TDX / attested
   <quote-hash>" is what an auditor wants to see.

## What this skill does NOT cover

- In-process safety (Layers 1–5) — see other skills.
- Layer 6 cross-hardware safeguards — see
  `../iaiso-layer-6-existential-safeguard/SKILL.md`.

## References

- `vision/docs/spec/06-layers.md`
- `vision/systems/hardware/{intel,amd,nvidia,arm}/`
- `known-limitations.md` — hardware-level anchors compose
  from outside the SDK
