# Migration Guide — IAIso 5.0 monorepo → two-zone layout

This document tells you which folders and files from the existing
`SmartTasksOrg/IAISO` repository move where in the new layout.

## Target layout

```
IAISO/
├── README.md         ← NEW (top-level signpost, provided)
├── NOTICE.md         ← NEW (explains the core/vision split, provided)
├── MIGRATION.md      ← NEW (this file)
├── LICENSE           ← UNCHANGED (keep at repo root)
├── core/             ← NEW (the working framework, provided)
└── vision/           ← NEW (everything from the old 5.0 repo goes here)
```

## Migration table

| Old path (current 5.0 repo)     | New path                              | Notes                                        |
|---------------------------------|---------------------------------------|----------------------------------------------|
| `README.md`                     | `vision/README.md`                    | Preserve verbatim; becomes the vision doc.   |
| `LICENSE`                       | `LICENSE`                             | Stays at repo root.                          |
| `sdk/`                          | `vision/sdk/`                         | Language SDK sketches; see relabel note.     |
| `plugins/`                      | `vision/plugins/`                     | Platform integration sketches.               |
| `systems/`                      | `vision/systems/`                     | Infra integrations (cloud/identity/ERP/…).   |
| `config/`                       | `vision/config/`                      | `l.env` and platform config sketches.        |
| `scripts/`                      | `vision/scripts/`                     | `quick-deploy.py`, `deploy-platform.sh`, etc.|
| `docs/` (old)                   | `vision/docs/`                        | Section 01–15 architecture docs.             |
| `LIVE-TEST/`                    | `vision/live-test/`                   | Demos; relabel as examples.                  |
| Solution packs (`sol.*`)        | `vision/solution-packs/`              | Collect under one folder.                    |
| Appendix A–F files              | `vision/appendices/`                  | Group together.                              |
| `.github/`                      | `.github/`                            | Keep at repo root if present.                |
| `.gitignore`                    | `.gitignore`                          | Keep/merge at repo root.                     |

## Step-by-step (git mv)

Run these from the root of your existing `IAISO` repo after cloning the
`iaiso-merged` scaffold on top.

```bash
# 0. Back up current state on a branch before reorganizing
git checkout -b reorg/two-zone-layout
git status    # confirm clean working tree

# 1. Move the old top-level README into vision/
git mv README.md vision/README.md

# 2. Move each top-level folder into vision/
#    (skip any folder that doesn't exist in your copy)
git mv sdk        vision/sdk
git mv plugins    vision/plugins
git mv systems    vision/systems
git mv config     vision/config
git mv scripts    vision/scripts
git mv docs       vision/docs
git mv LIVE-TEST  vision/live-test     2>/dev/null || true

# 3. Drop the new core/ folder in place (from iaiso-merged.zip)
#    unzip iaiso-merged.zip
#    cp -r iaiso-merged/core .
#    cp iaiso-merged/README.md iaiso-merged/NOTICE.md iaiso-merged/MIGRATION.md .

# 4. Commit the move as a pure rename (easier to review)
git add -A
git commit -m "reorg: split repo into core/ (shipped) and vision/ (design)"

# 5. Verify
cd core
pytest -q                      # 240 passed, 1 skipped expected
python -m iaiso.conformance spec/   # all 67 vectors pass
```

## Relabeling inside `vision/`

After the move, the sketchy code samples inside `vision/sdk/`,
`vision/plugins/`, and `vision/systems/` should be clearly marked so
nobody treats them as production code. Two options:

### Option A (recommended): rename files

```bash
# Example for Python SDK sketches
find vision/sdk -name '*.py' -not -name '*.example.py' \
  -exec rename 's/\.py$/.example.py/' {} +

# Example for JS SDK sketches
find vision/sdk -name '*.js' -not -name '*.example.js' \
  -exec rename 's/\.js$/.example.js/' {} +
```

This breaks accidental imports of the sketch files (since `.example.py`
isn't picked up by `import iaiso`). Intentional.

### Option B: wrap in `examples/` folders

```bash
mkdir -p vision/sdk/python/examples
git mv vision/sdk/python/iaiso/engine.py vision/sdk/python/examples/engine.py
```

Either works. Option A is fewer keystrokes if there are many files.

## Things to reconcile after the move

A handful of `vision/README.md` claims need editorial attention — not
because they're wrong as design intent, but because as prose they
promise capabilities that `core/` does not currently deliver. Suggested
edits:

1. **"80% market penetration" / "✅ Production" status badges** for
   SDKs and plugins.
   → Change to "Planned" or "Design target" status. The `vision/`
   zone should not assert production readiness.

2. **"Hardware-enforced compute caps (Layer 0) / BIOS-level FLOP
   limits"**.
   → Note that Layer 0 enforcement requires hypervisor/kernel work
   outside a Python library's reach. Keep as design intent; clarify
   that no current deployment enforces at the BIOS layer.

3. **"SOC 2 Type II / FedRAMP"**.
   → Compliance certifications attach to deployed systems audited by
   third parties, not to libraries. Reframe as: "`core/` emits audit
   events and supports controls that help operators meet these
   standards."

4. **"Catches 87% of unsafe reasoning chains (internal benchmarks)"**.
   → Either cite the benchmark and methodology, or delete the number
   and replace with qualitative language.

5. **Solution packs, platform plugins, language SDKs marked
   production-ready**.
   → Mark all as "roadmap / vision" consistently with the new NOTICE.

These edits live in `vision/README.md` and don't affect `core/` at all.
You can do them in a follow-up commit; the reorg stands on its own.

## What doesn't change

- Git history is preserved via `git mv` (rename detection).
- Issue tracker, releases, tags: unchanged. A release tag `v5.0.x`
  still points at a valid commit; a new tag `core-0.2.0` can be cut
  once the reorg lands.
- External links into the old README (e.g., "section 08") should be
  updated to `vision/docs/…` — grep for inbound links if any exist.

## After migration

The first green CI run on the reorganized branch is the proof the move
was clean. The most useful subsequent commits:

1. Update `vision/README.md` per the five edits above.
2. Add a `vision/NOTICE.md` (template provided at top of this repo's
   `NOTICE.md`) declaring `vision/` as non-shippable.
3. Set up CI to run `cd core && pytest` and
   `cd core && python -m iaiso.conformance spec/` on every PR.
4. Tag the merged state as `v5.1.0` (or whichever number makes sense
   for continuity) with changelog pointing to this reorg.
