# IAIso Specification

**Version: 1.0** · Normative source for the IAIso protocol.

This directory is the **contract**. The Python package in `iaiso/` is a
reference implementation of this contract. A port to another language
(Node, Go, Rust, Java, C++, …) is "IAIso-conformant" when it passes the
test vectors in this directory.

The human-readable prose in `docs/spec/` was the previous source of truth
and is now derivative. Where `docs/spec/*.md` and `spec/*/README.md`
disagree, `spec/` wins and `docs/spec/` is a bug.

## What is specified here

| Subsystem      | Normative artifact                        | Test vectors              |
|----------------|-------------------------------------------|---------------------------|
| Pressure math  | [`pressure/README.md`](pressure/README.md)| `pressure/vectors.json`   |
| Consent tokens | [`consent/README.md`](consent/README.md)  | `consent/vectors.json`    |
| Audit events   | [`events/README.md`](events/README.md)    | `events/vectors.json`     |
| Policy files   | [`policy/README.md`](policy/README.md)    | `policy/vectors.json`     |
| Coordinator    | [`coordinator/README.md`](coordinator/README.md) | (Redis keyspace)   |

Each subsystem ships:

1. **Prose spec** (`README.md`) — what the thing does, what the invariants
   are, what error cases look like. Intended for implementer reading.
2. **Machine-checkable schema** (`*.schema.json` in JSON Schema 2020-12)
   where the subsystem has a wire format. Implementations MUST produce
   outputs that validate against these schemas.
3. **Test vectors** (`vectors.json`) — concrete inputs and expected
   outputs. Implementations MUST pass every vector.

## What is NOT specified here

- **Language idioms.** Each port defines its own public API shape. The
  spec constrains *observable behavior* (what pressures, what events,
  what JWT payloads, what HTTP bodies to which sinks) and not method
  names or async style.
- **Middleware.** `iaiso.middleware.*` wrappers for specific LLM SDKs are
  per-language adaptations. They are not part of the protocol; they just
  feed inputs into the bounded execution.
- **Audit sinks beyond the envelope.** The spec defines the wire format
  of a single `AuditEvent`. It does not define how an implementation
  talks to Splunk, Datadog, Loki, etc. — that is a bytes-on-the-wire
  question answered by each vendor's documentation, and the Python
  reference implements it for Python.
- **Performance.** The spec does not promise ops/s, latency, or memory
  bounds. See `bench/` for what the reference implementation actually
  measures.

## Versioning

The spec uses a single `MAJOR.MINOR` version in `spec/VERSION`.

- **MINOR** bumps add new event kinds, new optional claims, new policy
  fields, new test vectors. Existing vectors MUST continue to pass.
- **MAJOR** bumps may break: change a pressure formula, rename a claim,
  change event envelope, remove a policy field. A v2.0 vector set will
  be shipped alongside and implementations must choose which version
  they target.

Pre-1.0 (i.e. right now) the spec may change on any release; compatibility
is best-effort. Projects embedding IAIso should pin the spec version.

## Tolerance for floating-point pressure math

Pressure computations are specified as real-number arithmetic. Floating-
point implementations MUST match the reference to within:

```
|p_impl - p_spec| ≤ 1e-9
```

in absolute terms. This is looser than bit-exact (which would require
mandating IEEE-754 evaluation order across all target languages and is
not reasonable) but tight enough that threshold behavior is indistinguishable
from the reference across any realistic workload.

Tighter tolerances (bit-exact) are allowed. Looser tolerances are not.

Ports written in integer/fixed-point arithmetic (e.g., embedded targets)
may use scaled integers provided they document the scaling and the
resulting quantization error, and the quantization error is bounded by
the 1e-9 tolerance.

## Running the conformance suite

From Python:

```bash
pip install iaiso
python -m iaiso.conformance spec/
```

Or as part of the reference test suite:

```bash
pytest tests/test_conformance.py -v
```

A port in another language needs to implement its own vector runner. See
`docs/CONFORMANCE.md` for the porting workflow.

## Stability statement

A vector file in `spec/*/vectors.json` is normative. It may be **extended**
(new vectors appended) at MINOR bumps. Existing vectors will not be
silently edited; if the reference-implementation behavior changes in a
way that makes a vector wrong, that is a MAJOR event and is announced.

## License

The specifications in this directory are licensed the same as the
surrounding project (see `../pyproject.toml`). You may implement this
specification in any language without restriction beyond the license
terms.
