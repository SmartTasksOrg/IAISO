---
name: iaiso-port-language-idioms
description: "Use this skill when adapting a working IAIso port to feel idiomatic. Do not use it before 67/67 conformance — idioms before conformance hide bugs."
version: 1.0.0
tier: P3
category: porting
framework: IAIso v5.0
license: See ../LICENSE
---

# Idiomatic adaptation of an IAIso port

## When this applies

The port passes all 67 vectors and now needs to feel like
natural code in the target language.

## Steps To Complete

1. **Pick an idiomatic resource pattern** for BoundedExecution:

   - Python: context manager (`with`).
   - Go: closure-callback (`Run(opts, fn)`).
   - Rust: RAII guard / scope-bound builder.
   - Java: try-with-resources via `AutoCloseable`.
   - C#: `using` via `IDisposable`.
   - Ruby: block form (`BoundedExecution.run do |e| ... end`).
   - PHP: callback style; or factory + explicit close.
   - Swift: `@MainActor` / structured concurrency block.

2. **Pick idiomatic naming.** Python: snake_case. Go:
   PascalCase exported / camelCase unexported. Java/C#:
   camelCase methods. Rust: snake_case. The conformance
   suite does not check names; users do.

3. **Pick idiomatic error types.** Don't force one
   hierarchy across languages. Python exceptions, Go error
   returns, Rust `Result`, Java checked exceptions.

4. **Match the language's logging / observability culture.**
   Python: `logging` module hooks. Go: `slog`. Java:
   SLF4J. Rust: `tracing`.

5. **Document the idiomatic surface in the SDK README.**
   Cross-reference back to the reference (Python) for
   readers translating examples.

## What this skill does NOT cover

- Conformance — that comes first. See
  `../iaiso-port-new-language/SKILL.md`.

## References

- existing nine reference ports as exemplars
