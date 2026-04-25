# NOTICE — Two-Zone Repository

This repository is intentionally split into two zones with different
status and different rules. Read this before copying code from either.

## `core/` — claim-backed, installable, supported

Everything in `core/` is expected to:

- Have passing tests (run `pytest` inside `core/`).
- Match its own README. If the README describes a feature, the code
  implements it and a test exercises it.
- Conform to the machine-checkable specification at
  `core/spec/` (run `python -m iaiso.conformance core/spec/`).

If you find a gap between a claim and the code, that is a bug and we
want to hear about it.

## `vision/` — design, roadmap, and historical record

Everything in `vision/` is:

- **Not installable.** No `pyproject.toml`, no `package.json`, no
  release artifacts. Do not `pip install`, `npm install`, or otherwise
  deploy anything from this zone.
- **Not tested.** Code examples inside `vision/` are pedagogical. They
  may be wrong, simplified, or entirely aspirational.
- **Not supported.** Bugs in vision material are welcome but not
  urgent; this is design copy, not running software.

Treat `vision/` as a design notebook. When a concept from `vision/`
earns working code, it moves into `core/` under the graduation process
described in the top-level README.

## Why this split exists

IAIso's repository began with ambitious positioning — a broad cross-
platform safety framework spanning many SDKs, integrations, and
compliance standards. Over time it became important to separate:

1. **What the code actually does today** (`core/`) — narrow, bounded,
   tested.
2. **What the project is aiming at long-term** (`vision/`) — wider,
   partly implemented, partly aspirational.

Conflating these was causing the README to over-promise relative to the
shipping code. The split is the fix: aspirational content is preserved
and has a legitimate home in `vision/`, but nothing can accidentally be
installed from there, and the top-level README points new users at the
zone that actually works.

## Rule of thumb for contributors

- Writing a README paragraph about a feature that isn't in `core/`?
  → `vision/`.
- Writing code that has a test? → `core/`.
- Writing code that sketches an idea? → `vision/` **with** a file name
  ending in `.example.*` or inside a folder called `examples/`.
- In doubt? Ask in an issue before committing.
