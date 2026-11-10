# IAIso Sandbox-Mediated Integration & Verification Spec

**Status:** Draft v0.1 — for review
**Scope:** Defensive. Authorized targets only (own repos, open-source projects under coordinated disclosure, and platforms accessed through their documented APIs with proper credentials).
**Relationship to IAIso:** This spec defines an *integration and verification layer* for the IAIso framework. It does not replace IAIso's SDKs, layers, or invariants; it provides a mechanical way to (a) bring IAIso controls into a target system at the deepest level that system allows, and (b) prove — in a hardened, network-isolated sandbox — that the control actually blocks the threat it claims to.

---

## 0. Purpose & Honest Framing

IAIso's thesis is *containment through structure, not trust*. The gap between that thesis and real-world impact is **adoption friction**: a framework only contains what it is actually wired into. Today IAIso ships SDKs and plugins, but wiring them into a heterogeneous platform landscape by hand is slow, and a control that is claimed but not verified provides no assurance.

This spec closes both gaps with one mechanism: **the sandbox.** The same hardened, network-isolated sandbox logic used to *verify vulnerabilities* (provision → build → test, self-healing dependencies, adaptive probes) is repurposed to *drive and verify integration*. For each target it answers three questions mechanically:

1. **Where can IAIso attach?** (integration-point discovery)
2. **At what depth?** (integration tiering)
3. **Does the attached control actually hold?** (confirmed-then-defended verification)

### 0.1 Reach: stated as a conditional, not a claim

This spec deliberately avoids penetration claims. The correct statement of scope is conditional:

> **If** IAIso controls were integrated across the platform families enumerated in §5 — programming-language runtimes, e-commerce, CMS, CRM, cloud, identity, ERP, monitoring, and the major agent orchestrators — the *addressable* autonomous-agent attack surface, weighted by those platforms' published user/market share, would approach ~80% of the commercial AI-agent ecosystem.

That is a statement about **addressable surface if integrated**, not about deployments that exist today. The value of this spec is precisely that it provides the *mechanism* to move from "addressable" toward "addressed," one verified integration at a time, with proof at each step. Current verified integrations are tracked in §8 (Evidence Ledger) and start from a small, honest base.

---

## 1. Design Principles

1. **Guard-first.** Every integration leads with the *defense* (attach the IAIso control), then demonstrates the threat it neutralizes. Offensive detail stays at mechanism level; no weaponization recipes ship in this spec or its artifacts.
2. **Verify, don't assert.** No integration is marked "protected" until the sandbox has shown the exploit firing **without** the control and blocked **with** it (the confirmed-then-defended pattern).
3. **Deepest tier available.** Attach IAIso at the most enforceable layer the target permits (native > strap-on > middleware). Record the tier honestly, because tier determines which IAIso layers/invariants can actually be enforced (§4.4).
4. **Isolation is load-bearing.** All build/test runs happen in hardened containers; the exploit-verification phase runs with **no network**, so a fired sentinel is provably local code execution, not exfiltration.
5. **Fail safe, fail honest.** A missing dependency, an unsupported loader, or an ambiguous result yields *inconclusive*, never a false "protected."
6. **Human sign-off gate.** Machine detects, integrates, and verifies; a human authorizes any outbound action (PR, disclosure, deployment). Non-negotiable.

---

## 2. Architecture Overview

```
                    ┌──────────────────────────────────────────────┐
                    │            Integration Orchestrator           │
                    │  (drives the pipeline, enforces sign-off gate) │
                    └───────────────┬──────────────────────────────┘
                                    │
        ┌───────────────┬──────────┼───────────────┬──────────────────┐
        ▼               ▼          ▼               ▼                  ▼
  ┌───────────┐  ┌────────────┐ ┌───────────┐ ┌──────────────┐ ┌──────────────┐
  │ Target     │  │ Integration│ │ IAIso      │ │  Sandbox      │ │  Evidence     │
  │ Acquirer   │  │ Point       │ │ Attach     │ │  Verifier     │ │  Ledger       │
  │            │  │ Discovery   │ │ (tiered)   │ │ (confirmed-   │ │ (logs, video, │
  │ clone/API  │  │             │ │            │ │  then-        │ │  attestation) │
  │            │  │             │ │            │ │  defended)    │ │               │
  └───────────┘  └────────────┘ └───────────┘ └──────────────┘ └──────────────┘
        │               │             │              │                  │
        └───────────────┴─────────────┴──────────────┴──────────────────┘
                                    │
                    ┌───────────────▼──────────────────┐
                    │   Hardened, network-isolated       │
                    │   container substrate (sandbox.py) │
                    │   provision → build → test          │
                    │   self-healing deps, adaptive probes│
                    └────────────────────────────────────┘
```

The container substrate already exists (`iaiso-sandbox/sandbox.py`, `provision.py`) and is proven: it provisions a per-repo image, runs a build phase (network=bridge) and a test phase (network=none), self-heals missing Python dependencies via the LLM fleet, and runs shape-adaptive agentic exploit probes. This spec adds the *integration* stages on top of that substrate.

---

## 3. Target Acquisition

A target is one of three kinds, and the kind determines how it enters the sandbox:

| Kind | Example | How it enters the sandbox | What can be verified |
| --- | --- | --- | --- |
| **Open-source repo** | a self-hosted agent server on GitHub | full clone, mounted read-only into the container | Full: real code paths, real loaders, real config sinks |
| **API-accessed platform** | a hosted CRM/commerce API | *not* cloned; a local mediator app is built in the sandbox that calls the platform's documented API with supplied credentials | The **mediator/middleware** is verified locally; the remote platform is exercised only through its sanctioned API |
| **Local system** | the operator's own stack composed of open repos + IAIso | assembled in the sandbox from the operator's components | Full, end-to-end, including cross-component flows |

**Rule:** Open-source repos are cloned and analyzed in full. Closed platforms are **never** probed adversarially against their live service — only their published API is called, and only the *local mediator* that wraps that API is exploited/verified in the sandbox. This keeps all adversarial testing inside the operator's own boundary.

---

## 4. Integration Tiers

IAIso attaches at the deepest tier the target permits. The orchestrator tries them in order and records which succeeded.

### 4.1 Tier 1 — Native / Direct Integration

The target has a first-class extension mechanism (plugin API, middleware hook, SDK), and IAIso ships a corresponding SDK/plugin.

- **Mechanism:** install the IAIso SDK/plugin for that platform; wire the control at the platform's own extension point.
- **Enforceable IAIso layers:** potentially all, depending on the platform (Layer 0 only if the platform exposes hardware/compute limits; Layers 2/3/3.5/4/5/6 via the SDK).
- **Example:** an agent framework (LangChain/CrewAI/AutoGen) where IAIso's wrapper composes around the agent loop.

### 4.2 Tier 2 — Modular Strap-On

The target has no IAIso-specific plugin but does expose an interposition surface: middleware, request/response hooks, an event bus, or a wrappable client.

- **Mechanism:** generate a thin adapter that routes the target's dangerous operations (model loads, tool calls, config writes, outbound requests) through the relevant IAIso control before they execute.
- **Enforceable IAIso layers:** Layer 2 (tool/expansion limits), Layer 5 (consent-scoped expansion), Layer 4 (escalation) — the *decision* layers. Not Layer 0.
- **Example:** wrapping a model-loading call so it passes through `assert_safe_load` (consent-bounded expansion, IAIso invariant #4) before `from_pretrained` executes.

### 4.3 Tier 3 — Snap-In Middleware (Proxy/Shim)

The target offers no clean extension point. IAIso interposes as a proxy/shim between the target and its dangerous sink.

- **Mechanism:** a middleware process (or import-shim) sits on the path between the agent and the resource — an inbound/outbound proxy for network sinks, or an import/loader shim for in-process sinks — and applies the IAIso control at the choke point.
- **Enforceable IAIso layers:** whatever passes through the choke point — typically Layer 5 consent checks and Layer 2 limits on the intercepted operation. Coverage is **partial by construction**: only sinks that traverse the shim are protected. This must be stated honestly in the evidence ledger.
- **Example:** an outbound-request middleware that enforces a consent-scoped allowlist on the endpoints an agent may call (mitigating agent-driven SSRF / endpoint redirection), when the agent framework has no hook to do so natively.

### 4.4 Honest tier→enforcement mapping

The tier is not cosmetic. It bounds what IAIso can actually promise:

| IAIso layer / invariant | Tier 1 native | Tier 2 strap-on | Tier 3 middleware |
| --- | --- | --- | --- |
| Layer 0 (hardware caps) | only if platform exposes it | ✗ | ✗ |
| Layer 2 (tool/expansion limits) | ✓ | ✓ | ✓ at choke point |
| Layer 4 (escalation bridge) | ✓ | ✓ | partial |
| Layer 5 (consent-scoped expansion) | ✓ | ✓ | ✓ at choke point |
| Layer 6 (existential safeguards) | rarely | ✗ | ✗ |
| Invariant #4 (consent-bounded expansion) | ✓ | ✓ | ✓ at choke point |
| Invariant #5 (no proxy optimization) | ✓ | partial | ✗ (shim *is* a proxy) |

The ledger records, per integration, the tier achieved and therefore the honest set of layers/invariants enforced. Claiming Layer 0 via a middleware shim, for instance, is prohibited.

---

## 5. Integration-Point Discovery (sandbox-driven)

For a cloned open-source target, the sandbox performs static + dynamic discovery to find where IAIso should attach. This reuses the existing mechanism-detection (windowed AST scan) and loader/shape detection from the verifier stack.

**Discovered sink categories** (each maps to an IAIso control):

| Sink category | What it is | IAIso control | Verifier probe |
| --- | --- | --- | --- |
| **Untrusted model provenance** | `from_pretrained` / loader with caller-supplied path + `trust_remote_code` | `model_provenance_guard` (Layer 5 consent-bounded load) | shape-adaptive evil-model probe (proven) |
| **Code / artifact loading** | dynamic import, plugin-by-name, package install of an agent-chosen name | consent-scoped load control | artifact-load probe |
| **Command / argument construction** | agent-built shell/SQL/path strings | command/path guards | injection probe |
| **Config mutation → privileged action** | agent writes config/allowlist/.env consumed later by a privileged op | two-stage consent control (write-time + use-time) | config-mutation probe (planned) |
| **Resource / endpoint redirection** | agent-supplied URL/endpoint → SSRF/exfil | endpoint allowlist (Layer 5) | endpoint-redirection probe |
| **Tool-result influence** | untrusted tool output steers the next agent action | consent re-validation on tool-result-derived actions | tool-result probe (research) |

Discovery outputs, per target: the list of sinks, their file:line, the loader/shape (for model sinks), the reachability ranking (server/agent-reachable > library-wrappable > human-CLI), and the recommended integration tier per sink.

---

## 6. Sandbox Verifier: Confirmed-Then-Defended

This is the heart of the spec and the part already proven end-to-end for the model-provenance class.

For each discovered sink, the sandbox runs the probe **twice**:

1. **Undefended run** (control *not* attached): exercise the target's real sink with a benign adaptive test artifact (e.g. a shape-matched local model whose custom code writes a sentinel — no network, no harm). If the sentinel fires, the sink is **confirmed reachable/exploitable** in this target.
2. **Defended run** (IAIso control attached at the chosen tier): repeat. The control must reject the operation *before* the sentinel fires. Sentinel silent + control-blocked = **defended**.

**Verdicts:**
- `CONFIRMED` — undefended fired; the vuln exists in this target.
- `DEFENDED` — undefended fired, defended blocked; the IAIso integration works.
- `NO-FINDING` — undefended did not fire; the sink is not reachable/exploitable here (honest negative).
- `INCONCLUSIVE` — environment/loader could not be exercised (missing dep beyond healing, unsupported loader, closed sink); never reported as protected.

**Isolation guarantee.** The test phase runs with `network=none`. A fired sentinel is therefore provably *local code execution*, not exfiltration — the same isolation property that made the reference finding trustworthy.

**Self-healing environment.** Missing Python dependencies are resolved automatically (known-map → LLM fleet → module-name fallback), bounded to avoid loops, so heterogeneous targets can be exercised without hand-tuning.

**Reference result (Evidence Ledger §8):** a self-hosted open-source LLM-serving repo was taken through this exact pipeline: its reranker model-load sink (`CrossEncoder(caller_path, trust_remote_code=True)`) was `CONFIRMED` in a network-isolated container, and `DEFENDED` once the model-provenance guard was attached at Tier 2. That is the first fully sandbox-verified IAIso integration for this class.

---

## 7. Pipeline (end to end)

```
1. ACQUIRE      → clone (OSS) or build API-mediator (closed); mount into sandbox
2. PROVISION    → pick toolchain image; prepare hardened container
3. DISCOVER     → find sinks (§5), rank reachability, choose tier per sink
4. VERIFY-PRE   → undefended run per sink → CONFIRMED / NO-FINDING
5. ATTACH       → wire the IAIso control at the deepest available tier (§4)
6. VERIFY-POST  → defended run per sink → DEFENDED / INCONCLUSIVE
7. REGRESS      → run target's own tests (if present) to prove integration didn't break it
8. LEDGER       → record tier, verdicts, layers enforced, logs, optional screen capture
9. SIGN-OFF     → human reviews the ledger; authorizes PR / disclosure / deploy
```

Stages 2–7 are fully mechanical and run in the sandbox. Stage 9 is a hard human gate. No outbound artifact (PR to an OSS project, disclosure, production deploy) is emitted without it.

---

## 8. Evidence Ledger (what "verified" means, and what proof ships)

Every integration produces a ledger entry. This is the artifact a reviewer, an OSS maintainer, or a standards body receives. It is designed to be *reproducible* and *mechanism-level*, never a weaponization guide.

Ledger entry fields:
- Target identity + commit/API version
- Integration tier achieved (§4) and therefore layers/invariants honestly enforced (§4.4)
- Per-sink verdicts (CONFIRMED / DEFENDED / NO-FINDING / INCONCLUSIVE)
- Sandbox logs: provision, build (deps + any self-healed packages), undefended run, defended run, isolation attestation (`network=none` during test)
- Optional: screen recording of the confirmed-then-defended run (build → CONFIRMED → attach control → DEFENDED)
- Regression result (target's own tests pass post-integration)
- Reproduction command

**Proof discipline (dual-use caution).** The ledger demonstrates *that the class exists and the control holds*, using a benign sentinel. It does **not** include real payloads, agent-manipulation recipes, or escape techniques. Techniques matching this class are already used by real adversaries; the responsible artifact is the guard-first, mechanism-level proof, disclosed coordinated rather than public-first.

---

## 9. Middleware Reference Design (Tier 3 snap-in)

When neither native nor strap-on integration is possible, IAIso ships as a snap-in middleware. Two forms:

### 9.1 In-process import/loader shim
Interposes on a dangerous in-process sink (e.g. model loading). On the intercepted call, the shim applies the IAIso control (consent-scoped allowlist, fail-closed) before delegating to the real loader. Coverage = the sinks the shim wraps; stated explicitly.

### 9.2 Out-of-process proxy
Sits on the network path between the agent and external resources. Enforces a consent-scoped endpoint allowlist and rate/expansion limits (Layer 2/5) on outbound calls the agent initiates. Mitigates agent-driven endpoint redirection / SSRF where the framework has no native hook.

Both forms are **verified by the same sandbox probe** before they are trusted: the middleware is attached, the corresponding probe is run, and only a `DEFENDED` verdict certifies it. Middleware that cannot be shown to block its target class in the sandbox is not shipped as protection.

**Honest limitation.** Middleware enforces only at its choke point and cannot provide Layer 0 (hardware) or Layer 6 (existential) guarantees. It is a coverage-extending measure for environments that cannot integrate deeper — not equivalent to native containment, and labeled as such.

---

## 10. Relationship to IAIso taxonomy & standards

- Each verifier probe is authored as an **IAIso red-team probe** (the `iaiso-redteam-*` / RT-family convention). The model-provenance probe is the first.
- Each attached control is an **IAIso layer control** (the model-provenance guard = Layer 5 consent-bounded expansion, invariant #4). New sink categories map to their layer.
- Findings and controls carry **standards mappings** IAIso already declares: OWASP LLM Top-10 (agentic entries), MITRE ATLAS, NIST AI RMF, CWE (e.g. CWE-494 Download of Code Without Integrity Check, CWE-829 Inclusion of Functionality from Untrusted Control Sphere) for the model-provenance class.
- The vulnerability *class* is proposed to governing bodies under a **neutral, mechanism-based name**, with IAIso credited as the discovering/mitigating framework — not as a branded class name, which standards bodies do not adopt.

---

## 11. Non-Goals & Boundaries

- No adversarial testing against live third-party services — only OSS clones and operator-local API mediators.
- No automated outbound contact, mass reporting, or public-first disclosure. One target at a time, human-reviewed, coordinated, guard offered as the fix.
- No claims of enforcement beyond the achieved tier (§4.4).
- No penetration/market claims stated as fact; reach is conditional (§0.1).
- No weaponization detail in any shipped artifact.

---

## 12. Roadmap (honest status)

| Item | Status |
| --- | --- |
| Container substrate (provision/build/test, network-isolated) | Done, proven |
| Self-healing dependency loop | Done, proven |
| Model-provenance guard + tests | Done (guard well-tested) |
| Shape-adaptive agentic verifier (model-provenance) | Done, proven (1 target CONFIRMED→DEFENDED) |
| Integration-point discovery for other sink categories | Partial (model-provenance complete) |
| Config-mutation two-stage control + probe | Planned |
| Endpoint-redirection middleware + probe | Planned |
| Tool-result influence probe | Research |
| Orchestrator `--agentic-verify` gate wiring | Planned |
| Evidence ledger tooling (logs + capture bundle) | Planned |
| Coordinated disclosure of confirmed reference finding | Pending human sign-off |

---

*This spec is defensive-security engineering. It integrates and verifies protective controls, discloses responsibly, and states its scope and limits honestly. The sandbox is the mechanism that keeps every claim in it falsifiable.*
