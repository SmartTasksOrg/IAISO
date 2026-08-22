---
name: iaiso-verify-integration-tiers
description: "Use this skill to choose the deepest IAIso integration tier a target permits (native > strap-on > middleware) and to record the honest set of layers/invariants that tier can enforce. Do not use it to find sinks (see iaiso-verify-integration-discovery) or to claim enforcement the achieved tier does not support."
version: 1.0.0
tier: P1
category: verify
framework: IAIso v5.0
license: See ../LICENSE
---

# SmartFabric integration tiers

## When this applies

You know where IAIso should attach and must decide *how deeply*. Attach at
the deepest tier the target permits, try them in order, and record which
succeeded. The tier is load-bearing: it determines which IAIso layers and
invariants can actually be enforced.

## Steps To Complete

1. **Try tiers in order; record the one that succeeds.**

   - **Tier 1 — Native / direct.** The target has a first-class extension
     point (plugin API, middleware hook, SDK) and IAIso ships a matching
     SDK/plugin. Wire the control at the platform's own extension point.
   - **Tier 2 — Modular strap-on.** No IAIso plugin, but an interposition
     surface exists (middleware, request/response hooks, event bus,
     wrappable client). Generate a thin adapter that routes dangerous
     operations through the relevant IAIso control before they execute.
   - **Tier 3 — Snap-in middleware (proxy/shim).** No clean extension
     point. Interpose a proxy/shim on the path to the dangerous sink and
     apply the control at the choke point. See `iaiso-integ-middleware-reference`.

2. **Apply the honest tier→enforcement map.** Never claim more than the
   achieved tier supports:

   | Layer / invariant | Tier 1 native | Tier 2 strap-on | Tier 3 middleware |
   |---|---|---|---|
   | Layer 0 (hardware caps) | only if platform exposes it | ✗ | ✗ |
   | Layer 2 (tool/expansion limits) | ✓ | ✓ | ✓ at choke point |
   | Layer 4 (escalation bridge) | ✓ | ✓ | partial |
   | Layer 5 (consent-scoped expansion) | ✓ | ✓ | ✓ at choke point |
   | Layer 6 (existential safeguards) | rarely | ✗ | ✗ |
   | Invariant #4 (consent-bounded expansion) | ✓ | ✓ | ✓ at choke point |
   | Invariant #5 (no proxy optimization) | ✓ | partial | ✗ (shim *is* a proxy) |

3. **Prohibited claims.** Claiming Layer 0 via a middleware shim, or
   Layer 6 via a strap-on, is a false claim. Middleware coverage is
   *partial by construction* — only sinks that traverse the choke point.

4. **Write the achieved tier into the ledger** so the enforced layer set
   is honest and auditable. See `iaiso-verify-evidence-ledger`.

## What this skill does NOT cover

- Sink discovery — see `iaiso-verify-integration-discovery`.
- The verifier run — see `iaiso-verify-confirmed-then-defended`.
- Middleware construction detail — see `iaiso-integ-middleware-reference`.

## References

- `SMARTFABRIC.md`
- `SPEC-iaiso-sandbox-integration.md` §4, §4.4
- `../LIMITATIONS.md` (why in-process checks need a Layer 0 anchor)
