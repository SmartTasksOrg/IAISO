# IAIso Pressure Model — Normative Specification

**Version: 1.0**

This document specifies the deterministic pressure-accumulation model
that every IAIso-conformant implementation MUST implement. It is the
mathematical heart of the protocol: given the same configuration and
the same input sequence, every conformant implementation produces the
same pressure trajectory, the same threshold transitions, and the same
step outcomes.

Floating-point equality is within the `1e-9` absolute tolerance
specified in `spec/README.md`.

## 1. Domain

Pressure `p` is a real number in the closed interval `[0, 1]`.

## 2. Configuration

The engine is parameterized by a `PressureConfig` with the following
fields:

| Field                     | Type   | Range       | Default | Units                   |
|---------------------------|--------|-------------|---------|-------------------------|
| `escalation_threshold`    | real   | [0, 1]      | 0.85    | pressure                |
| `release_threshold`       | real   | [0, 1]      | 0.95    | pressure                |
| `dissipation_per_step`    | real   | ≥ 0         | 0.02    | pressure / step         |
| `dissipation_per_second`  | real   | ≥ 0         | 0.0     | pressure / second       |
| `token_coefficient`       | real   | ≥ 0         | 0.015   | pressure / 1000 tokens  |
| `tool_coefficient`        | real   | ≥ 0         | 0.08    | pressure / tool call    |
| `depth_coefficient`       | real   | ≥ 0         | 0.05    | pressure / depth level  |
| `post_release_lock`       | bool   | —           | true    | —                       |

**Validation.** An implementation MUST reject a config that violates:
- Either threshold is outside `[0, 1]`.
- `release_threshold ≤ escalation_threshold`.
- Any non-negative field is negative.

**Defaults are not empirically calibrated.** They produce reasonable
behavior on the reference scenarios in `evals/`. For any production
deployment, calibrate against measured workload traces. The spec does
not claim these defaults are correct for your workload — it only claims
that every conformant implementation processes them identically.

## 3. State

The engine holds the following state:

| Field            | Type                | Initial value          |
|------------------|---------------------|------------------------|
| `pressure`       | real in [0, 1]      | `0.0`                  |
| `step`           | non-negative int    | `0`                    |
| `lifecycle`      | enum Lifecycle      | `INIT`                 |
| `last_delta`     | real                | `0.0`                  |
| `last_step_at`   | real (clock units)  | `clock()` at init      |

### 3.1 Lifecycle enum

```
INIT       # fresh, no steps taken yet
RUNNING    # accepting steps, pressure below escalation_threshold
ESCALATED  # accepting steps, pressure in [escalation_threshold, release_threshold)
RELEASED   # transient; emitted when crossing release_threshold
LOCKED     # refusing steps; only reset() escapes
```

`RELEASED` is a transient state that only appears in emitted audit events;
after a release the lifecycle is either `LOCKED` (when `post_release_lock`
is true) or `RUNNING` (otherwise).

### 3.2 StepOutcome enum

`step()` returns one of:

```
OK          # pressure below escalation_threshold after this step
ESCALATED   # pressure in [escalation_threshold, release_threshold) after this step
RELEASED    # pressure crossed release_threshold; state reset has already occurred
LOCKED      # engine was locked; this step did NOT advance state
```

## 4. The step equation

Let `p_{i-1}` be the pressure before step `i`, `t_{i-1}` the clock value
at the previous observation, and `StepInput_i = (tokens_i, tool_calls_i,
depth_i, tag_i)` the input. Let `C_tok`, `C_tool`, `C_depth`, `D_step`,
`D_time` be the configured coefficients.

The engine observes the clock: `t_i = clock()`.

Compute the elapsed time since the last observation, clamped non-negative:

```
elapsed_i = max(0, t_i - t_{i-1})
```

Compute delta (pressure added this step, before decay):

```
delta_i = (tokens_i / 1000) * C_tok
        + tool_calls_i * C_tool
        + depth_i * C_depth
```

Compute decay (pressure removed this step):

```
decay_i = D_step + elapsed_i * D_time
```

Update pressure:

```
p_i = clamp(p_{i-1} + delta_i - decay_i, 0, 1)
```

where `clamp(x, lo, hi) = max(lo, min(x, hi))`.

Update state:

```
step        ← step + 1
last_delta  ← delta_i - decay_i        # NOTE: net, not gross
last_step_at ← t_i
lifecycle   ← RUNNING                   # always — overwritten below if threshold crossed
```

### 4.1 Evaluation order

The spec describes real-number arithmetic. Implementations in
floating-point languages MUST evaluate `delta_i` as three non-negative
contributions summed together, in any order, and `decay_i` as `D_step +
elapsed_i * D_time`. The spec does not mandate a specific IEEE-754
evaluation order — any order that gets within the `1e-9` tolerance is
conformant.

### 4.2 Units of the clock

The clock returns real numbers in seconds. Monotonic clocks (e.g.,
Python `time.monotonic`, POSIX `CLOCK_MONOTONIC`, Go `time.Now()` with
care for wall-clock adjustments, Rust `Instant`) are RECOMMENDED.
Wall-clock sources are acceptable if the environment has no clock
adjustments; conformant test vectors use an explicit scripted clock so
this does not matter for conformance.

## 5. Outcome determination

Immediately after state update, evaluate thresholds in this order:

1. If `p_i ≥ release_threshold`:
   - Emit `engine.release` (payload: `pressure = p_i`, `threshold`).
   - Set `pressure ← 0`.
   - If `post_release_lock`: set `lifecycle ← LOCKED`, emit `engine.locked`.
     Otherwise: set `lifecycle ← RUNNING`.
   - Return `RELEASED`.

2. Else if `p_i ≥ escalation_threshold`:
   - Set `lifecycle ← ESCALATED`.
   - Emit `engine.escalation` (payload: `pressure = p_i`, `threshold`).
   - Return `ESCALATED`.

3. Else:
   - `lifecycle` remains `RUNNING` (was set in §4).
   - Return `OK`.

Both thresholds are inclusive on the lower bound: `p_i = 0.85` with the
default escalation threshold is an escalation. `p_i = 0.95` with the
default release threshold is a release.

## 6. Locked state

If `lifecycle == LOCKED` when `step()` is called:

1. Emit `engine.step.rejected` (payload: `reason = "locked"`,
   `requested_tokens`, `requested_tools`).
2. Do NOT advance the step counter.
3. Do NOT update `pressure`, `last_delta`, or `last_step_at`.
4. Return `LOCKED`.

The caller escapes by calling `reset()`.

## 7. reset()

`reset()`:

1. Set `pressure ← 0`.
2. Set `step ← 0`.
3. Set `last_delta ← 0`.
4. Set `last_step_at ← clock()`.
5. Set `lifecycle ← INIT`.
6. Emit `engine.reset` (payload: `pressure = 0`).

## 8. Emitted events

Every state transition emits an event. The normative envelope and
payloads are specified in `spec/events/`. For the pressure engine
specifically, the event kinds and their trigger points are:

| Event kind              | Triggered at                                        |
|-------------------------|-----------------------------------------------------|
| `engine.init`           | End of engine construction.                         |
| `engine.step`           | End of §4 state update, before threshold checks.    |
| `engine.escalation`     | Case 2 of §5.                                       |
| `engine.release`        | Case 1 of §5, before pressure is zeroed.            |
| `engine.locked`         | Case 1 of §5 when `post_release_lock` is true.      |
| `engine.step.rejected`  | §6, when a step is refused due to `LOCKED`.         |
| `engine.reset`          | End of §7.                                          |

The event stream for a given input sequence is deterministic and is part
of the conformance contract.

## 9. Determinism guarantees

Given identical:

- `PressureConfig`
- `execution_id`
- Input sequence of `StepInput`s
- Observed clock values at every `clock()` call

every conformant implementation produces:

- Identical pressure trajectories (within `1e-9`).
- Identical step outcomes.
- Identical emitted audit events (up to timestamp; see `spec/events/`
  for which fields participate in the equality).

Non-determinism MAY enter via:

- Real wall-clock or monotonic clock sources (not observed in test
  vectors, which script the clock).
- Concurrent access from multiple threads. Engines are NOT thread-safe;
  one engine per execution.

## 10. Test vectors

`spec/pressure/vectors.json` specifies concrete input sequences and the
expected state/outcome/event trajectory after each step. A conformant
implementation reads the file and runs each vector against its own
engine, passing every one.

Vector format:

```json
{
  "version": "1.0",
  "vectors": [
    {
      "name": "single_small_step_is_ok",
      "description": "One 100-token step with default config stays nominal.",
      "config": { /* PressureConfig fields; missing fields take defaults */ },
      "clock": [0.0, 0.1],
      "steps": [
        { "tokens": 100, "tool_calls": 0, "depth": 0, "tag": null }
      ],
      "expected": [
        {
          "step": 1,
          "pressure": 0.0,
          "lifecycle": "running",
          "outcome": "ok",
          "delta": 0.0015,
          "decay": 0.02
        }
      ]
    }
  ]
}
```

See `spec/pressure/vectors.json` for the full set.

## 11. Non-goals

The pressure model explicitly does NOT provide:

- **Hardware-level enforcement.** The engine runs in the same process as
  the agent it bounds. A sufficiently compromised agent can bypass it.
  For stronger isolation, sandbox the agent (gVisor, Firecracker, separate
  process) and enforce IAIso at the sandbox boundary.
- **Cryptographic state attestation.** The engine does not prove to an
  external observer that it entered a given state. For tamper-evident
  archival, sign or hash-chain the event stream externally.
- **Cross-execution coordination.** Each engine is independent. For
  fleet-wide pressure, see `spec/coordinator/`.
- **Regulatory compliance.** Running this engine does not make a system
  compliant with any regulation.
