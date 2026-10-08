# How to apply this bundle

This bundle is built on top of your merged `main`. Two safe paths:

## Option A — the patch (recommended)

`remediation.patch` is **additive only: zero deletion hunks.** It cannot remove
anything, so your Git client will show a clean diff with no red minuses.

```bash
cd /path/to/IAISO
git apply --check -p1 remediation.patch   # dry run
git apply -p1 remediation.patch
```

## Option B — merge-overlay the tree

```bash
cp -a IAIso-v5.0/. /path/to/IAISO/     # merges into directories
rsync -a IAIso-v5.0/ /path/to/IAISO/   # also merges
```

Do **not** extract in a way that swaps whole directories, and never use
`rsync --delete`. That is what removed `core/docs/`, both `tests/` directories,
and `core/iaiso-node/bin/` last time.

## Verify

```bash
cd core/iaiso-go     && go build ./... && go vet ./... && go test ./... \
                     && go run ./cmd/iaiso-conformance ./spec     # 72/72
cd ../iaiso-python   && pytest -q                                 # 257 passed
cd ../iaiso-node     && npm exec -- tsc --noEmit && npm test              # 195 passed
```

`tests/test_redis_coordinator.py` fails 8 tests with `unknown command 'evalsha'`.
That is pre-existing — it fails identically on the unmodified repository. The
installed `fakeredis` has no Lua support.

## One thing to reconcile by hand

`core/docs/THREAT_MODEL.md` and the new root-level `LIMITATIONS.md` both contain
a threat model. Two that disagree is worse than one that is blunt. Read them side
by side and fold one into the other; `core/docs/known-limitations.md` is now a
tombstone pointing at `LIMITATIONS.md`.
