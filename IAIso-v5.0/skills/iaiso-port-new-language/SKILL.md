---
name: iaiso-port-new-language
description: "Use this skill when porting IAIso to a new programming language. Triggers on \"port to <language>\", new SDK creation, conformance implementation. Do not use it for fixing an existing port — see `iaiso-spec-conformance-vectors` for the test surface."
version: 1.0.0
tier: P3
category: porting
framework: IAIso v5.0
license: See ../LICENSE
---

# Porting IAIso to a new language

## When this applies

A new SDK in a language not yet covered by the nine reference
ports (Python, Node, Go, Rust, Java, C#, PHP, Ruby, Swift).

## Steps To Complete

1. **Read the spec hub first.** `core/spec/README.md` and
   each subsystem README are normative. Resolve any
   ambiguity by reading the conformance vectors.

2. **Build the pressure engine first.** It is the foundation;
   every other subsystem depends on it. Pass all 20 pressure
   vectors before moving on.

3. **Build consent next.** 23 vectors. Use a JOSE library
   that supports both HS256 and RS256 and rejects `none`.

4. **Build events.** 7 vectors. The envelope is small; the
   payload schemas are larger — implement them as data
   classes / structs / records.

5. **Build policy.** 17 vectors. The cross-field validation
   (release > escalation, both in [0,1]) is where ports
   most often miss.

6. **Build the BoundedExecution surface.** It composes the
   engine, consent verifier, and audit sink. The reference
   SDK's class shape is a good starting point; idiomatic
   adaptation is fine.

7. **Run all 67 vectors green.** No vector is optional. If
   a vector seems wrong, it isn't — open an issue against
   the spec rather than skipping it.

8. **Add idiomatic ergonomics LAST.** A `with` block in
   Python, `defer` in Go, RAII in Rust, try-with-resources
   in Java. Don't bake idioms in before conformance is solid.

## What this skill does NOT cover

- Vector authoring — see
  `../iaiso-spec-conformance-vectors/SKILL.md`.
- Per-language idioms — see
  `../iaiso-port-language-idioms/SKILL.md`.

## References

- `core/spec/README.md`
- any of the nine reference ports as exemplars
- `core/docs/CONFORMANCE.md`
