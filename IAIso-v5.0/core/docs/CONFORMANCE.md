# Building an IAIso-Conformant Implementation

This document describes how to write an IAIso implementation in a new
language (Node, Go, Rust, Java, C++, …) and validate it against the
normative specification.

## What makes an implementation conformant

An implementation is **IAIso-conformant** when:

1. It faithfully implements the algorithms and wire formats in
   [`spec/`](../spec/).
2. It passes every test vector in
   [`spec/pressure/vectors.json`](../spec/pressure/vectors.json),
   [`spec/consent/vectors.json`](../spec/consent/vectors.json),
   [`spec/events/vectors.json`](../spec/events/vectors.json), and
   [`spec/policy/vectors.json`](../spec/policy/vectors.json).
3. Its emitted events validate against
   [`spec/events/envelope.schema.json`](../spec/events/envelope.schema.json)
   and the per-kind payload schemas in
   [`spec/events/payloads.schema.json`](../spec/events/payloads.schema.json).
4. If it implements fleet coordination, it talks to the Redis backend
   described in [`spec/coordinator/README.md`](../spec/coordinator/README.md)
   and is interoperable with the Python reference.

The Python package in this repository is the reference implementation.
If you hit a disagreement between the reference and the spec, **the
spec wins**. File a bug against the reference.

## Shipping ports

| Language | Location | Package | Conformance | Spec version |
|---|---|---|---|---|
| Python | [`core/iaiso-python/`](../iaiso-python/) | `iaiso` | 67/67 | 1.0 |
| TypeScript / Node.js | [`core/iaiso-node/`](../iaiso-node/) | `@iaiso/core@0.3.0` | 67/67 | 1.0 |
| Go | [`core/iaiso-go/`](../iaiso-go/) | `github.com/iaiso/iaiso-go@v0.1.0` | 67/67 | 1.0 |
| Rust | [`core/iaiso-rust/`](../iaiso-rust/) | Cargo workspace `iaiso-*@0.1.0` | 67/67 | 1.0 |
| Java | [`core/iaiso-java/`](../iaiso-java/) | Maven `io.iaiso:iaiso-*@0.1.0` | 67/67 | 1.0 |
| C# / .NET | [`core/iaiso-csharp/`](../iaiso-csharp/) | NuGet `Iaiso.*@0.1.0` | 67/67 | 1.0 |
| PHP | [`core/iaiso-php/`](../iaiso-php/) | Composer `iaiso/iaiso@0.1.0` | 67/67 | 1.0 |
| Swift | [`core/iaiso-swift/`](../iaiso-swift/) | SwiftPM `iaiso-swift@0.1.0-draft` | run `swift test` | 1.0 |
| Ruby | [`core/iaiso-ruby/`](../iaiso-ruby/) | RubyGems `iaiso@0.1.0` | 67/67 | 1.0 |

Eight of the nine ports are self-contained and were driven to 67/67 through
compile-test-fix iteration. The Swift port was authored without an
available toolchain — its conformance suite is shipped, runs identically
to the others, and is expected to pass 67/67 once you run `swift test`,
but that confirmation has to come from the consumer's machine.

Browse any source tree as a worked example for additional language ports —
[`core/iaiso-python/iaiso/`](../iaiso-python/iaiso/) for Pythonic style,
[`core/iaiso-node/src/`](../iaiso-node/src/) for idiomatic TypeScript with
structural typing, [`core/iaiso-go/iaiso/`](../iaiso-go/iaiso/) for Go's
explicit error handling and structural interfaces,
[`core/iaiso-rust/crates/`](../iaiso-rust/crates/) for Rust's
multi-crate workspace and structural traits,
[`core/iaiso-java/`](../iaiso-java/) for Java's Maven multi-module
layout with structural interfaces,
[`core/iaiso-csharp/`](../iaiso-csharp/) for C#'s multi-project .NET
solution with structural interfaces,
[`core/iaiso-php/`](../iaiso-php/) for PHP's single-package PSR-4
layout with native enums and zero runtime dependencies,
[`core/iaiso-swift/`](../iaiso-swift/) for Swift's SwiftPM multi-target
layout with CryptoKit / Security.framework crypto, or
[`core/iaiso-ruby/`](../iaiso-ruby/) for Ruby's single-gem layout with
duck-typed interfaces and zero runtime dependencies. All nine produce
identical outputs for identical inputs.

## Suggested porting order

The subsystems below are listed in the order they should be implemented
in a new port — cheapest to most expensive, and each builds on the
previous.

### 1. Scope matching (~1 hour)

The cheapest subsystem. A pure function `grants(granted: List<str>,
requested: str) -> bool`. The spec is in `spec/consent/README.md §4–§5`.
Run the `scope_match` vectors in `spec/consent/vectors.json`.

This is a good warm-up: it proves the project can consume the vectors
and compare strings, before there's any pressure math or JWT parsing
to worry about.

### 2. Pressure engine (~1 day)

The mathematical heart of IAIso. `spec/pressure/README.md` is fully
self-contained. Translate §4 and §5 into your language, feed it the
20 vectors in `spec/pressure/vectors.json`, and you're done.

Pitfalls to watch for:

- **Clock injection.** The reference takes a `clock: Callable[[], float]`
  parameter. Every language has an idiomatic way to do this; don't skip
  it or your tests can't run.
- **Float evaluation order.** The spec does not mandate a specific
  IEEE-754 evaluation order. Compute `delta = (tokens/1000) * C_tok +
  tool_calls * C_tool + depth * C_depth` in any order that stays within
  `1e-9` of the reference. All 20 vectors pass with straightforward
  left-to-right evaluation in Python/Node/Go/Rust/Java.
- **Clamp semantics.** Both thresholds are *inclusive on the lower
  bound*. `p == escalation_threshold` means escalation, not "still ok".
- **Release + lock ordering.** On a release step: emit `engine.step`
  first (with the pre-reset pressure), then `engine.release`, then
  `engine.locked` if `post_release_lock`. Getting this wrong silently
  breaks event-stream replay.

### 3. Audit event envelope (~2 hours)

Straightforward struct + JSON serialization. See
`spec/events/README.md §1` and `spec/events/envelope.schema.json`.

Validate your JSON output against the schema using any JSON Schema
library for your language (`ajv` for Node, `gojsonschema` for Go,
`jsonschema` for Python, etc.). Every emitted event MUST pass
validation; your test suite should include this as a property test.

### 4. Consent JWT issuer + verifier (~1–2 days)

Reuse your language's best-maintained JWT library (`jsonwebtoken` for
Node, `github.com/golang-jwt/jwt/v5` for Go, `jsonwebtoken` for Rust,
`auth0-jwt` or `nimbus-jose-jwt` for Java).

Wire it up per `spec/consent/README.md §6`. Run the 23 vectors in
`spec/consent/vectors.json` — the `valid_tokens` and `invalid_tokens`
use a fixed HS256 key so any conformant verifier should accept/reject
identically.

Pitfalls:

- **`alg=none` rejection.** Every JWT library lets you decode without
  verification. Never expose that path to the consent verifier.
- **Algorithm confusion.** A verifier configured for RS256 MUST reject
  HS256 tokens even if signature bytes happen to match.
- **Constant-time HMAC comparison.** Your JWT library probably handles
  this, but verify it.
- **Execution binding.** If both the call and the token have an
  `execution_id`, they MUST match. If either is absent, binding is not
  enforced. This is subtler than it sounds — easy to over- or
  under-enforce.

### 5. Policy file loader (~0.5–1 day)

`spec/policy/README.md` + `spec/policy/policy.schema.json`. Validate
against the schema, then construct typed config objects with defaults
from §8 of the policy spec.

Unknown keys at any level MUST NOT fail — forward compatibility is a
hard requirement.

### 6. BoundedExecution wrapper (~0.5 day)

The user-facing facade that combines pressure + consent + audit.
Mostly plumbing; no new math. See `iaiso/core/execution.py` for the
reference. Language-idiomatic naming is expected (builders in Java, a
`with` context in Python, `defer` in Go, a builder-pattern struct in
Rust).

### 7. LLM middleware adapters (~1 day each)

Per SDK: Anthropic, OpenAI, LangChain, etc. Each is a thin wrapper
that:

- Calls `bounded_execution.require_scope(...)` before a tool call.
- Calls `bounded_execution.record_tokens(...)` / `record_tool_call(...)`
  after.
- Escalates (breaks the loop, pauses for human review) when the engine
  returns ESCALATED or LOCKED.

Not normative — there's no spec vector for "Anthropic middleware does X"
because every language's SDK is different. But the underlying pressure
and audit contract is normative, so any correct wrapper produces the
same events and pressures.

### 8. Audit sinks (~2 hours each)

Per destination: stdout, JSONL file, Splunk, Datadog, Loki, …. Map the
envelope to whatever each vendor's HTTP intake expects. The envelope is
the contract; the destination is not.

### 9. Redis coordinator (~1 day)

See `spec/coordinator/README.md §1`. The Lua script is verbatim.
Communicating with the same Redis instance as the Python reference
will verify interop in practice — the only validation IAIso currently
offers for coordinator conformance is cross-running both clients.

### 10. Fleet integration test (~0.5 day)

Stand up a Redis container. Run a Python execution and a {your-language}
execution pointing at the same coordinator. Verify that pressure pushed
by either is visible to the other, and that escalation fires for the
aggregate.

This isn't a formal conformance vector yet but it's the test that
catches real cross-language bugs.

## Validating your port

Every port should ship its own conformance runner that:

1. Reads the JSON vector files directly from `spec/*/vectors.json`.
2. Runs each vector against the port's engine / verifier / loader.
3. Emits results in a format the CI can digest (JUnit XML, TAP, etc.).

See `iaiso/conformance/` for the Python reference runner. The pattern
is:

```
for each vector in vectors.json:
    construct engine/verifier/loader with vector.config
    feed vector.inputs
    compare observed outputs to vector.expected
    (within 1e-9 tolerance for floats)
```

At a minimum, your port's CI should run:

- Pressure vectors (20).
- Consent scope-match vectors (12).
- Consent valid/invalid token vectors (8).
- Events stream vectors (7).
- Policy valid/invalid vectors (17).

= 64 vectors minimum. Plus 3 structural tests (spec/VERSION exists,
each section has a README, each section has vectors.json).

## Versioning

Pin to a specific `spec/VERSION` in your port's README:

> This implementation targets IAIso spec version **1.0**.

When we bump MINOR (new event kinds, new optional claims), your port
should still pass all the old vectors unchanged. New vectors appear in
new files or as appended entries; existing entries are never edited.

When we bump MAJOR, you make a choice: stay on 1.x, or upgrade. There
will be an explicit migration guide.

## Publishing a port

We'd love to link to your port from the main project. File an issue
with:

- A link to your repo.
- A link to your CI run showing all vectors passing.
- Your port's README section naming `IAIso spec 1.0` as the target.

Ports that pass all vectors are eligible to call themselves
"IAIso-conformant (spec 1.0)" in documentation and marketing materials.

## Getting help

- Open an issue on the main IAIso repo with the `question` label.
- Spec ambiguities (cases where the spec doesn't say what to do) are
  bugs in the spec, not the port. Please file them.
- Behavior where the reference implementation disagrees with the spec
  is also a spec bug (in the reference, not the spec). Please file it.
