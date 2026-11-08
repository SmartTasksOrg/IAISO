---
name: iaiso-runtime-back-prop-magnification
description: "WITHDRAWN. 'Back-propagation magnification' was an early design concept and is not implemented in the reference engine. The `enable_backprop` / `enable_magnification` flags are accepted as no-ops for backward compatibility and the SDK warns if you set them. Do not route to this skill for a runtime behavior; it exists only to document that the feature was withdrawn."
version: 2.0.0
tier: P0
category: runtime
framework: IAIso v5.0
license: See ../LICENSE
---

# Back-propagation magnification — withdrawn (not implemented)

**This feature does not exist in the reference engine.** Earlier
documentation described a recursive "magnification" refinement loop,
said to run when `BACK_PROPAGATION=true`, that would score and refine
outputs and feed a `D_magnified = D_base · (1 + β · ∇Q)` term back into
the pressure model. **None of that is implemented.**

- There is no `magnification.py` module and no `apply_magnification`,
  `magnify`, or quality-gradient function anywhere in the core SDK.
- `PressureWrapper(..., enable_backprop=...)` and
  `ConsentScope(..., enable_magnification=...)` accept the argument
  for backward compatibility, treat it as a **no-op**, and emit a
  warning telling you to remove it.
- The pressure model's dissipation is passive per-step decay plus an
  entropy floor. There is no quality-gradient enhancement term.

## What to do instead

IAIso's job is **mechanical containment** — bounded compute pressure,
structural resets, lifetime caps, and the out-of-process enforcement
proxy — not content refinement. Output-quality checks belong in your
own harness or evaluation pipeline (for example an LLM-judge step or a
tool such as promptfoo), outside the containment engine.

## Status

Withdrawn in the honesty pass that aligned the documentation with the
code. This file is retained so that older links and router entries
resolve to an accurate explanation rather than a 404. It describes no
runtime behavior and should not be followed as a procedure.
