# Backwards Compatibility Policy

IAIso follows a **semver-with-deprecation-windows** policy. This file
describes what it means for something to be public API, how long we
support it, and what users of different versions can expect.

## Versioning

We use `MAJOR.MINOR.PATCH`:

- **PATCH** (0.1.0 → 0.1.1): bug fixes, internal refactors, new tests,
  documentation improvements. No public API changes.
- **MINOR** (0.1.0 → 0.2.0): new features, new classes, new sink/
  middleware/coordinator backends. Existing public APIs do not break.
- **MAJOR** (0.1.0 → 1.0.0): breaking changes allowed. Described in
  CHANGELOG.md with migration notes.

## What is public API

**Public** (stable, subject to this policy):

- Everything directly under `iaiso`, `iaiso.audit`, `iaiso.core`,
  `iaiso.consent`, `iaiso.coordination`, `iaiso.metrics`,
  `iaiso.observability`, `iaiso.policy`, `iaiso.reliability`,
  `iaiso.identity`, `iaiso.cli`, `iaiso.middleware.*`,
  `iaiso.calibration` that is NOT prefixed with an underscore.
- The audit event schema, versioned by `AuditEvent.schema_version`.
- The policy file format, versioned by the `version` field.
- The CLI's argument structure for documented subcommands.

**Private** (may change in any release):

- Anything prefixed with `_` (e.g., `engine._pressure`).
- Internal module names under submodules not listed above.
- Docstrings' internal examples that are not also in `docs/`.

## Pre-1.0 policy (currently in effect)

IAIso is currently **0.x**. During this phase:

- **MINOR bumps may contain small breaking changes** when we catch
  design mistakes. Each such change is called out in CHANGELOG.md
  under a "⚠️ Breaking" heading with a migration snippet.
- Breaking changes are batched into MINOR bumps rather than being
  applied PATCH-to-PATCH, so `pip install "iaiso~=0.1.0"` (any 0.1.x)
  is always safe.
- The goal is to reach a stable 1.0 by when: (a) the audit event schema
  has shipped in production with at least one user; (b) the policy
  format has been stable for 3+ months; (c) we have real benchmark
  numbers from non-synthetic workloads.

## Post-1.0 policy (target)

Once we reach 1.0:

- **MINOR bumps MUST NOT break public API.** New functions, new
  parameters with defaults, and new optional config fields are OK.
- **Deprecations require a full minor release of warning** before
  removal in the next MAJOR. Example: a function deprecated in 1.4
  can be removed in 2.0, not in 1.5.
- Deprecated APIs use `warnings.warn(... DeprecationWarning)` at call
  time, plus `# deprecated: reason, remove in X.Y` in a module-level
  comment.

## Event schema stability

Every audit event carries a `schema_version` field. Consumers should:

1. Accept any `schema_version` ≤ the one they were built against
   (forward-compatible: new fields are added, old fields are not
   removed within a MAJOR).
2. Warn on `schema_version` greater than expected, then continue
   processing (extra fields are just ignored).

Schema bumps:

- **Minor schema change** (e.g., `"1.0"` → `"1.1"`): add a field. No
  version bump of the library required.
- **Major schema change** (e.g., `"1.0"` → `"2.0"`): rename or remove
  a field. Library bumps MAJOR.

## Policy file stability

The top-level `version` field in policy files tracks policy format,
not library version. A library at 1.3.0 can still accept `version: "1"`
policy files indefinitely. New policy versions ship with a migration
tool (`iaiso policy migrate`) when the jump is worth automating.

## Deprecation labels (examples)

```python
def old_thing(*args, **kwargs):
    """Deprecated: use new_thing() instead. Remove in 2.0."""
    import warnings
    warnings.warn(
        "old_thing() is deprecated and will be removed in 2.0. "
        "Use new_thing() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return new_thing(*args, **kwargs)
```

## What we don't promise

- **Python version support.** We support currently-supported upstream
  Python versions. A Python release going EOL is not a breaking change
  for us.
- **Transitive dependency APIs.** If `prometheus_client` changes its
  `Counter` class, our `PrometheusMetricsSink` may need to change
  with it. That adaptation is a patch-level release from our side.
- **Middleware compatibility with SDK major versions.** If Anthropic
  releases a v5 SDK with breaking changes, we ship an adapter — but
  that adapter might be a new class (`AnthropicV5BoundedClient`) not
  a silent upgrade of the existing one.

## How to tell if a change is breaking

When in doubt, the test is: _does every piece of code that previously
worked still work, untouched?_ If no → breaking. If yes → not breaking.
