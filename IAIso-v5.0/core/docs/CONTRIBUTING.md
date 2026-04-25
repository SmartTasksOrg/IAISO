# Contributing to IAIso

Thanks for considering a contribution. This guide covers what we're
looking for, how to propose changes, and what the review bar is.

## What we're looking for

**Good contributions** usually fall into one of these categories:

1. **Bug fixes with regression tests.** Not just "fix" but "fix + test
   that would have caught it."
2. **New middleware for LLM SDKs that exist today** (we accept these
   readily) or **new SIEM/identity integrations** (if you have a real
   deployment that needs them).
3. **Better documentation**, especially for real-world gotchas we
   haven't hit yet.
4. **Performance improvements with benchmarks showing the improvement**
   (not just "this should be faster").
5. **New aggregators, sinks, or backends** that fit the existing
   interfaces.

**Not great** (we'll probably decline):

- New features that don't fit an existing interface and haven't been
  discussed in an issue first.
- Silent behavior changes to existing public API.
- Refactors that change the shape of the public API without a
  migration path.
- "Enterprise" features that depend on compliance certifications or
  vendor partnerships that belong in separate distributions.

## How to propose a change

### Small changes (single file, <100 lines diff)

1. Open a PR directly with a description of what and why.
2. Tests must cover the change.
3. Maintainers will review within ~a week.

### Larger changes (multiple files, API surface, new subsystems)

1. **Open an issue first** describing the problem you want to solve.
2. Wait for a maintainer to confirm the shape before writing code.
3. PR against the shape agreed on in the issue.

Skipping step 1 for large changes is the most common cause of PRs
being rewritten. A day spent aligning on the interface up front saves
a much larger rework cycle during review.

## The review bar

Every PR is checked against this list:

- [ ] **Tests pass.** `python -m pytest` clean, including the new
      tests for the change.
- [ ] **Types pass** if your change adds typed code. `mypy` config
      is in `pyproject.toml`.
- [ ] **Public API is documented.** Every new public function, class,
      or module has a docstring. The docstring explains what it does,
      not just what each parameter is.
- [ ] **Claims are verified.** If you add a middleware for
      "Provider X," the docs describe exactly what was verified
      end-to-end. Capability descriptions match what the code and
      tests demonstrate.
- [ ] **No dead code.** If a module isn't used and isn't exported,
      delete it or explain why it's there.
- [ ] **Consistent style.** We use Python 3.12 type syntax (`X | Y`
      not `Optional[X]`), `from __future__ import annotations` at
      the top of every module, and prefer explicit over implicit.
- [ ] **Security-sensitive changes flagged.** Anything touching
      `iaiso.consent`, `iaiso.audit`, or `iaiso.identity` gets extra
      scrutiny. Call it out in the PR description.

## Style notes

- Modules start with a docstring explaining purpose and expected
  usage. If you can't write one without hand-waving, the design
  probably isn't clear enough yet.
- Public APIs do not expose internal machinery. If you find yourself
  documenting `execution._engine._pressure`, you're documenting
  something private; pick a better public surface or ensure the
  private state is reachable through a proper method.
- Error messages are sentences, with punctuation, that describe what
  the caller did wrong and how to fix it. Not `ValueError("x")`.
- Logging / audit events are structured. Do not use `print()`,
  do not use `logging.info("Something happened: %s", thing)` where a
  structured audit event would be more useful.

## Things that commonly surprise contributors

### 1. We prefer slightly more duplication over premature abstraction

Two similar middleware classes that share 80% code but differ in how
they extract tokens is usually fine. A base class that tries to
unify them — and then has three ifs inside for provider-specific
branches — is usually worse.

### 2. We don't accept "production-ready" claims in docstrings

Say what the code does. Do not say "production-ready," "battle-tested,"
"enterprise-grade," etc. The reader can judge.

### 3. We don't add optional dependencies lightly

Every new extra in `pyproject.toml` is a maintenance burden.
Prefer using standard library or an existing dependency before
adding a new one.

### 4. Real end-to-end tests matter more than high mock coverage

Mocks can drift from reality. If your change adds a SIEM sink for a
vendor you use in production, run it against the real vendor once
before you send the PR and say so. We'll believe you.

### 5. We sometimes say no to good ideas

Not because the idea is bad but because it doesn't fit this project's
scope. We're deliberately keeping IAIso narrow: pressure-bounded
execution for agents. A proposal that says "IAIso should also do X"
for some broader X is usually better as a separate library that
depends on IAIso.

## Setting up a development environment

```bash
git clone https://github.com/your-org/iaiso
cd iaiso

python -m venv .venv
source .venv/bin/activate

pip install -e ".[dev,metrics,otel,policy,redis,oidc,anthropic,openai,litellm,langchain,splunk,datadog,elastic]"

python -m pytest          # should be green
python -m iaiso --help    # CLI smoke test
python -m iaiso.bench.microbench --quick  # benchmark smoke test
```

## Reporting security issues

Do **not** open a public issue for security-sensitive findings.
Instead, email security@your-org.example (replace with actual address
when forking). We'll acknowledge within 3 business days and coordinate
disclosure per CERT/CC guidance.

## License and CLA

By submitting a pull request, you agree to license your contribution
under the terms in LICENSE. We do not currently require a separate CLA.

## Thanks

Tests, documentation, honest bug reports, and small cleanups are all
genuinely helpful. If you're not sure whether a contribution is
wanted, open an issue and ask.
