# IAIso Policy Files — Normative Specification

**Version: 1.0**

A policy file is a YAML or JSON document that configures an IAIso
deployment. It lets ops teams manage IAIso configuration with the same
tools they use for everything else: version control, code review,
template engines, secret managers, GitOps pipelines.

Policy files cover three subsystems:

1. **Pressure engine** — coefficients and thresholds.
2. **Coordinator** — fleet-wide aggregate thresholds and the aggregator.
3. **Consent** — issuer identity, default TTL, required scopes.

## 1. File format

A policy file is a JSON document. YAML is accepted iff YAML is a
strict superset of JSON for the subset used here (no anchors, no merge
keys, no YAML-specific types). If a YAML parser is not available, an
implementation MUST accept JSON with the same structure.

File extensions:

- `.json` — JSON
- `.yaml`, `.yml` — YAML
- Any other extension — implementations MUST reject with a clear error.

The top-level document MUST be a mapping (JSON object). A top-level
array or scalar is invalid.

## 2. Top-level structure

```yaml
version: "1"            # REQUIRED; must be exactly "1" for this spec version
pressure:               # OPTIONAL; defaults applied per spec/pressure
  ...
coordinator:            # OPTIONAL; defaults applied per subsystem
  ...
consent:                # OPTIONAL
  ...
metadata:               # OPTIONAL; passthrough, implementation-defined
  ...
```

Unknown top-level keys MUST cause the loader to emit a warning but NOT
to fail. This allows forward-compatible additions.

Unknown keys inside known sections MUST also NOT fail. (This is the
same forward-compatibility posture as events §2.)

## 3. pressure section

```yaml
pressure:
  token_coefficient: 0.015         # number, >= 0. Default 0.015.
  tool_coefficient: 0.08           # number, >= 0. Default 0.08.
  depth_coefficient: 0.05          # number, >= 0. Default 0.05.
  dissipation_per_step: 0.02       # number, >= 0. Default 0.02.
  dissipation_per_second: 0.0      # number, >= 0. Default 0.0.
  escalation_threshold: 0.85       # number, [0, 1]. Default 0.85.
  release_threshold: 0.95          # number, [0, 1]. Default 0.95.
  post_release_lock: true          # boolean. Default true.
```

All fields are optional. Missing fields take the defaults from
`spec/pressure/README.md §2`.

Cross-field validation (spec/pressure §2): `release_threshold` MUST
exceed `escalation_threshold`. If a policy file violates this, the
loader MUST raise a validation error.

## 4. coordinator section

```yaml
coordinator:
  escalation_threshold: 5.0        # number, >= 0. Default depends on aggregator.
  release_threshold: 8.0           # number, >= 0. Default depends on aggregator.
  notify_cooldown_seconds: 1.0     # number, >= 0. Default 1.0.
  aggregator: sum                  # enum: sum | mean | max | weighted_sum
  weights: {exec-vip: 2.0}         # object, used only if aggregator=weighted_sum
  default_weight: 1.0              # number. Used only if aggregator=weighted_sum.
```

Aggregators behave per `iaiso.coordination`:

- `sum` — sum of all execution pressures.
- `mean` — arithmetic mean.
- `max` — maximum.
- `weighted_sum` — per-execution weights, defaulting to `default_weight`.

Defaults for coordinator thresholds are NOT universal — they depend on
aggregator choice. The reference implementation uses 5.0/8.0 for `sum`,
but a `mean` aggregator should have thresholds in [0, 1]. Policy authors
MUST set thresholds explicitly; a loader MAY warn if thresholds look
inconsistent with aggregator choice but MUST NOT fail.

## 5. consent section

```yaml
consent:
  issuer: "my-org"                       # string. If set, becomes the ConsentVerifier issuer.
  default_ttl_seconds: 3600              # number, >= 0. Default 3600.
  required_scopes: [tools.read]          # array of scope strings.
  allowed_algorithms: [HS256, RS256]     # array of string; enum of supported algs.
```

`required_scopes` is a policy-level hint. It does NOT enforce that every
issued token contains these scopes — that is the application's
responsibility. Loaders simply expose the list.

## 6. metadata section

`metadata` is a free-form mapping for tagging. Implementations MUST
preserve it but MUST NOT interpret it.

Typical uses: `environment: prod`, `owner: platform-team`, cost
allocation tags.

## 7. Validation errors

A loader MUST raise a distinct error type (`PolicyError` in the Python
reference, or equivalent) with a path pointer when validation fails.
The path pointer uses JSON-Pointer-like syntax:

```
$.pressure.escalation_threshold: 1.5 > maximum 1
$.coordinator.aggregator: 'median' not in ['sum', 'mean', 'max', 'weighted_sum']
$.consent.required_scopes[0]: expected string, got integer
```

The exact message wording is not normative, but:

- The path component MUST be present and MUST identify the offending
  field.
- The error type MUST be distinguishable from runtime errors (it's a
  config-time problem, fail fast at startup).

## 8. Defaults — canonical table

When a field is missing, implementations MUST apply these defaults:

| Path                                   | Default                              |
|----------------------------------------|--------------------------------------|
| `pressure.token_coefficient`           | `0.015`                              |
| `pressure.tool_coefficient`            | `0.08`                               |
| `pressure.depth_coefficient`           | `0.05`                               |
| `pressure.dissipation_per_step`        | `0.02`                               |
| `pressure.dissipation_per_second`      | `0.0`                                |
| `pressure.escalation_threshold`        | `0.85`                               |
| `pressure.release_threshold`           | `0.95`                               |
| `pressure.post_release_lock`           | `true`                               |
| `coordinator.notify_cooldown_seconds`  | `1.0`                                |
| `coordinator.aggregator`               | `"sum"`                              |
| `coordinator.default_weight`           | `1.0`                                |
| `consent.default_ttl_seconds`          | `3600`                               |
| `consent.required_scopes`              | `[]`                                 |
| `consent.allowed_algorithms`           | `["HS256", "RS256"]`                 |
| `metadata`                             | `{}`                                 |

`coordinator.escalation_threshold` and `coordinator.release_threshold`
are OPTIONAL when the `coordinator` section is present. When omitted,
they default to `5.0` and `8.0` respectively — values calibrated for
the `sum` aggregator. If both are specified, `release_threshold` MUST
exceed `escalation_threshold`; a loader MUST raise a validation error
otherwise.

## 9. Test vectors

`spec/policy/vectors.json` contains:

- **Valid policies**: input document + expected parsed config values.
- **Invalid policies**: input document + expected error path / message
  substring.

A conformant loader passes all valid vectors (parsed values match the
expectations within `1e-9` tolerance for numbers) and rejects every
invalid vector with an error that includes the expected path substring.

## 10. Examples

See `iaiso/policy/__main__.py --template` or the CLI:

```
python -m iaiso policy template > policy.yaml
```

which emits a fully-annotated minimal policy with all defaults written
out.
