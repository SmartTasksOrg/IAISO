# Moved → `/LIMITATIONS.md`

This file has been replaced by [`../../LIMITATIONS.md`](../../LIMITATIONS.md) at
the repository root.

The old document was titled "SDK Scope and Architecture" and reframed every
limitation as a design choice. Its architecture content is preserved in
`LIMITATIONS.md`, but it is now preceded by a threat model that states plainly
what IAIso does **not** protect against — most importantly, that an agent
executing arbitrary code inside the agent process is **not contained** by any
in-process check.

There were two copies of this file (here and at the repository root). Both are
now stubs. Delete them once inbound references have been updated.
