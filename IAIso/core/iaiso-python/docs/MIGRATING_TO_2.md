# Migrating from IAIso 1.x / 0.3 to 2.0

2.0 turns the hardening options into defaults. Nothing is removed; every 1.x
behaviour is one call away.

| Area | 1.x | 2.0 default | Keep 1.x |
|---|---|---|---|
| Empty steps | dissipate pressure | do not | `PressureConfig.v1(...)` or `empty_step_dissipation=True` |
| Model not in `model_costs` | free | highest listed price | `unpriced_model_usd_per_million=0.0` |
| Lifetime caps | none | none, but boot guard warns (strict refuses) | set `max_total_*` or `budget_usd` + `model_costs` |
| Consent algorithm | HS256 | inferred from key; shared secret needs `algorithm="HS256"` | `ConsentIssuer.v1(...)` |
| Consent audience | optional | required on issuer and verifier; token needs `aud` | `ConsentVerifier.v1(...)` |
| Unbound token for an execution | accepted | refused | `require_execution_binding=False` |
| CLI `consent issue` with no key | ephemeral secret (crashed) | refused; use `iaiso consent keygen` | — |

New: `reserve()/commit()/cancel()`, `engine.totals`, `PressureWrapper(agent_factory=...)`,
`python -m iaiso.proxy`.

Conformance: `spec/pressure/vectors.json` (1.x) replays under `PressureConfig.v1`;
`vectors-2.json` pins 2.0; `hostile.json` is shared by all ports.
