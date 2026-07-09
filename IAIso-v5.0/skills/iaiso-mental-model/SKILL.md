---
name: iaiso-mental-model
description: "Use this skill when a teammate or agent needs the IAIso concepts — pressure as accumulation, the coin-pusher analogy, the layers, the invariants — before touching code. Do not use it for implementation tasks; load a spec or runtime skill instead."
version: 1.0.0
tier: P0
category: foundation
framework: IAIso v5.0
license: See ../LICENSE
---

# The IAIso mental model

## When this applies

The reader does not yet know what pressure means or how the
layers fit together. Once they do, switch to a spec or runtime
skill — this one is foundation, not implementation.

## Steps To Complete

1. **Read out the core equation in plain English.**

   ```
   dp/dt = Input − Dissipation − Release
   ```

   Pressure `p(t)` is a real number in `[0, 1]`. It rises with
   tokens emitted, tool calls invoked, and planning depth. It
   falls passively (dissipation per step and per second) and
   drops to zero atomically when a release fires.

2. **State the four lifecycle states verbatim** — they show up
   on every audit event:

   - `INIT` — fresh, no steps yet.
   - `RUNNING` — accepting steps, below escalation threshold.
   - `ESCALATED` — accepting steps, between escalation and
     release thresholds.
   - `LOCKED` — refusing steps; only `reset()` escapes.

3. **State the four step outcomes** — the values your code
   branches on after every `step()`:

   - `OK`        — pressure stayed below escalation.
   - `ESCALATED` — pressure entered the escalation zone.
   - `RELEASED`  — pressure crossed release; state was reset.
   - `LOCKED`    — engine was locked; step did not advance.

4. **State the four threshold zones** with their default
   boundaries:

   | Zone        | Range            | Behaviour                                    |
   |-------------|------------------|----------------------------------------------|
   | Nominal     | `p < 0.70`       | autonomous execution, standard friction      |
   | Warning     | `0.70 ≤ p < 0.85`| throttling, increased logging                |
   | Escalation  | `0.85 ≤ p < 0.95`| Layer 4 triggered, multi-party auth required |
   | Release     | `p ≥ 0.95`       | atomic reset, memory wipe, session lock      |

   The numbers are defaults — every deployment calibrates them
   (see `iaiso-deploy-calibration`).

5. **State the seven layers** so the listener can place a
   feature when they hear it:

   | Layer | Name                  | Where it lives                                  |
   |-------|-----------------------|-------------------------------------------------|
   | 0     | Physical Boundaries   | hardware / hypervisor / OS, outside the SDK     |
   | 1     | Optimization Bounds   | gradient clipping, entropy floor, back-prop     |
   | 2     | Memory & Planning     | depth gates, tool-expansion limits (in SDK)     |
   | 3     | Ecosystem Coupling    | coordinator, multi-agent (in SDK)               |
   | 3.5   | Regime Shift          | phase-transition monitoring                     |
   | 4     | Escalation Bridge     | human-in-the-loop authorization (in SDK)        |
   | 5     | Self-Governance       | ConsentScope JWTs (in SDK)                      |
   | 6     | Existential Guards    | singleton prevention, replication caps          |

6. **State the five core invariants verbatim** — these are the
   contract every IAIso-conformant system preserves:

   1. **Bounded Pressure** — `p(t) ≤ P_max` always.
   2. **No Learning Across Resets** — every release is a lossy
      wipe; persistence requires Layer 5 consent.
   3. **Clocked Evaluation Only** — safety checks at discrete
      intervals; no continuous ungoverned loops.
   4. **Consent-Bounded Expansion** — every tool call requires
      a cryptographically signed ConsentScope.
   5. **No Proxy Optimization** — pressure is computed at OS
      level so the model cannot game the safety valve.

   Violation of any invariant triggers automatic Layer 4
   escalation.

## The coin-pusher analogy in one paragraph

Imagine a coin-pusher arcade machine. Coins (intelligence)
accumulate on a platform (system state). As the pile grows,
pressure builds. At a threshold, the mechanism triggers a
controlled release — coins fall, pressure resets. The frame
itself provides the hard edge that prevents overflow. Safety
through mechanical structure, not intent.

## What IAIso does not do

Teach this at the same time as the analogy, never after it. The coin-pusher
image is seductive and invites the listener to hear "containment". It is not.

IAIso is an **in-process accounting layer**. It runs inside the agent process
and depends on that process calling it. A boundary holds whether or not the
thing inside it cooperates; a convention holds only while it does. IAIso is a
convention that produces excellent telemetry.

| Adversary | Contained? |
|---|---|
| Runaway loop, recursion, retry storm | **Yes** — pressure accumulates, release fires |
| Budget overrun on a priced model | **Yes**, with `model_costs` and `budget_usd` |
| Missing audit trail | **Yes** — every step emits an event |
| Tool call outside granted scope | **Yes**, where `require_scope()` guards the call site |
| Agent executing arbitrary code (`bash`, `eval`, `subprocess`) | **NOT contained** — it can skip the accounting call |
| Agent that simply never calls `record_tokens()` | **NOT contained** — nothing enforces the call |
| Malicious operator setting `token_coefficient: 0` | **NOT contained**, by design — policy is trusted input |
| Compromised process | **NOT contained** — same address space as the accounting |
| Prompt injection steering the agent | **NOT contained** — pressure does not read intent |
| Uncalibrated coefficients | **NOT contained** — thresholds never fire, or always fire |

Containment is out-of-process: containers, seccomp, network allowlists,
read-only mounts, short-lived credentials, an out-of-process kill switch. IAIso
composes with those. It replaces none of them.

**Where it belongs:** in the harness — the loop that executes tool calls, or a
proxy in front of the model API. There the agent gets no vote about whether
accounting happens. Not inside the agent as a library the agent is trusted to
invoke upon itself.

If someone asks for containment, say plainly that IAIso is the wrong tool and
name the right ones. A safety framework whose gates silently do nothing is worse
than no framework, because it produces confidence.

## What this skill does NOT cover

- Any code. Move to `iaiso-spec-*` or `iaiso-runtime-*` once
  the listener has the mental model.
- Boot-time refusal — see `iaiso-deploy-enforcement-mode`.

## References

- `vision/README.md` — the original framework spec
- `core/spec/pressure/README.md` — the math, normatively
- `LIMITATIONS.md` — the threat model, normatively
