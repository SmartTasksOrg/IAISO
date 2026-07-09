# Moved → `LIMITATIONS.md`

This file has been replaced by [`LIMITATIONS.md`](LIMITATIONS.md).

The old document was titled "SDK Scope and Architecture" and reframed every
limitation as a design choice. Its architecture content is preserved in
`LIMITATIONS.md`, but it is now preceded by a threat model that states
plainly what IAIso does **not** protect against — most importantly, that an
agent executing arbitrary code inside the agent process is **not contained**
by any in-process check.

A second copy of the old document lived at `core/docs/known-limitations.md`;
it is now a stub pointing here too.

These stubs exist only so that existing links do not break. Delete them once
inbound references have been updated.
