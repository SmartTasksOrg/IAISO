# IAIso — Intelligence Accumulation Isolation & Safety Oversight

**Mechanical AI safety through pressure-control governance.** IAIso treats
agentic AI systems like high-pressure engines — measuring compute
accumulation and enforcing automatic safety releases when thresholds are
breached. Safety through structure, not hope.

This repository contains the full IAIso framework in two coordinated parts:

| Directory | Contents |
|---|---|
| **[`vision/`](vision/)** | The **IAIso 5.0 framework specification** — architecture, layer model, invariants, pressure equations, solution-pack catalog, integration reference designs, regulatory mappings, and supporting documentation. This is the normative design material. |
| **[`core/`](core/)** | The **reference SDK** — a Python implementation of the framework's runtime, with a machine-checkable specification directory, 240 passing tests, and 67 conformance vectors. Install this to run IAIso today. |

**Working with code?** Start in [`core/`](core/).
**Learning the framework?** Start in [`vision/`](vision/).

## Quick start

```bash
cd core
pip install -e .
python -m iaiso.conformance spec/   # 67 conformance vectors
pytest -q                            # 240 passing tests
```

Minimal usage:

```python
from iaiso import BoundedExecution, PressureConfig

with BoundedExecution.start(config=PressureConfig()) as execution:
    outcome = execution.record_tool_call(name="search", tokens=500)
    if outcome.name == "ESCALATED":
        # Layer 4: request human review per the escalation template
        ...
```

See [`core/README.md`](core/README.md) for the full SDK feature set and
[`core/docs/CONFORMANCE.md`](core/docs/CONFORMANCE.md) for the workflow
that ports the reference implementation to other languages.

## Repository structure

### `vision/` — IAIso 5.0 framework specification

The complete framework as designed: the pressure-accumulation model, the
7-layer containment architecture (Layer 0 through Layer 6), the 5 core
invariants, the coin-pusher mental model, 100+ industry solution packs,
28+ system integration reference designs, the full compliance mapping,
and sections 01–15 of the architecture documentation plus appendices
A–F.

`vision/` is the **design source**. It describes what IAIso is, how it
works conceptually, what reference patterns exist for each integration
target, and how the framework maps to regulatory standards. Code samples
in `vision/` are reference patterns illustrating the design. Running
implementations of those patterns live under `core/` once they are
built, tested, and verified against the conformance suite.

### `core/` — reference SDK and conformance suite

A Python package that implements the IAIso runtime: pressure engine,
consent tokens, audit events, policy-as-code, admin CLI, coordinator,
middleware for eight LLM providers, and sinks for seven SIEM platforms.
Every feature is backed by a test. Every wire format — pressure math,
JWT claims, audit events, policy files — has a JSON Schema and test
vectors in [`core/spec/`](core/spec/) that define the contract.

Running `python -m iaiso.conformance core/spec/` executes 67
machine-verifiable vectors against the implementation. Any port of
IAIso into another language (Node, Go, Rust, Java, …) is considered
conformant when it passes the same vectors.

## Framework growth

New capabilities move through the framework in a predictable path:

1. **Design** — the concept is specified in `vision/`: architecture,
   layer placement, reference patterns, example configurations.
2. **Specification** — where the capability has a wire format (an event,
   a token, a policy field, a coordinator message), it gets a JSON
   Schema and conformance vectors under `core/spec/<subsystem>/`.
3. **Implementation** — the runtime lands in `core/iaiso/` with tests.
   The full suite (`pytest` + `python -m iaiso.conformance core/spec/`)
   must pass.
4. **Release** — `core/CHANGELOG.md` records the addition;
   `core/spec/VERSION` increments (MINOR for additive, MAJOR for
   breaking) if the contract changed.
5. **Cross-language parity** — language ports land under
   `core/ports/<language>/` (when opened). Each port re-runs the
   conformance vectors in its own CI.

This keeps the framework's design work and its running code in
lockstep: the vision grows by being built out, and the code grows by
being specified first.

## What's in each SDK release

IAIso 0.2.0 (the current `core/` release) provides:

- **Pressure engine** with deterministic math and 20 conformance
  vectors.
- **Consent tokens** (HS256 / RS256 JWTs) with 23 conformance vectors.
- **Audit envelope** with JSON Schema and 7 event-stream vectors.
- **Policy-as-code** loader with JSON Schema and 17 vectors.
- **Middleware** for Anthropic, OpenAI, LangChain, LiteLLM, Google
  Gemini, AWS Bedrock, Mistral, and Cohere.
- **Audit sinks** for stdout, JSONL, Splunk, Datadog, Elastic Common
  Schema, Grafana Loki, Sumo Logic, New Relic, and generic webhooks.
- **In-memory and Redis-backed** cross-execution coordinator with
  atomic Lua update path.
- **Prometheus metrics** and **OpenTelemetry tracing**.
- **Deployment templates** for Docker, Helm, and Terraform.
- **Admin CLI** (`python -m iaiso`) for policy validation, token
  issue/verify, audit tailing, and coordinator inspection.
- **OIDC identity** integration for Okta, Auth0, and Azure AD.

See [`core/README.md`](core/README.md) for the full list.

## Upcoming from the roadmap

Priorities for subsequent SDK releases include:

- Conformant ports into Node.js, Go, Rust, and Java.
- Additional platform integration patterns graduating from `vision/` to
  `core/`: expanded CRM (Salesforce, HubSpot) adapters, e-commerce
  (Shopify, Magento) adapters, and CMS (WordPress, Drupal) adapters.
- Calibrated default coefficients from published benchmark studies.
- Coordinator gRPC sidecar (the proto is drafted in
  `core/spec/coordinator/wire.proto`).
- Industry solution-pack runtime loader, turning the `vision/`
  solution-pack JSONs into policy files consumable by the SDK.

Follow [`core/CHANGELOG.md`](core/CHANGELOG.md) for releases.

## Contributing

The highest-value contributions graduate material from `vision/` to
`core/`: pick a reference pattern, implement it with tests and (where
it has a wire format) a spec entry with conformance vectors, and open
a PR. Smaller contributions — design edits in `vision/`, SDK bug fixes
in `core/`, new conformance vectors — are also welcome.

See [`core/docs/CONTRIBUTING.md`](core/docs/CONTRIBUTING.md) for the
review bar and coding standards.

## License

Community Forking License v2.0. See [`LICENSE`](LICENSE).

Public forking is required. Private forks require written agreement.
All framework invariants must be preserved across forks.

## Repository layout

```
IAISO/
├── README.md               ← this file
├── MIGRATION.md            ← guide for consolidating older layouts
├── LICENSE
├── l.env                   ← global configuration reference
├── mkdocs.yml              ← documentation site configuration
├── core/                   ← reference SDK (Python, installable)
│   ├── iaiso/              ← package source
│   ├── spec/               ← normative specification + conformance vectors
│   ├── tests/              ← 240 passing tests
│   ├── docs/               ← SDK documentation
│   ├── bench/              ← benchmarks
│   ├── deploy/             ← Docker, Helm, Terraform templates
│   ├── pyproject.toml
│   ├── README.md
│   └── CHANGELOG.md
└── vision/                 ← framework specification
    ├── README.md           ← the IAIso 5.0 design
    ├── docs/               ← architecture docs (sections 01–15, appendices A–F)
    ├── components/         ← JSON component registry + 100+ solution packs
    ├── templates/          ← prompt templates for solution packs and systems
    ├── integrations/       ← AI framework reference designs
    ├── systems/            ← platform integration reference designs
    ├── examples/           ← industry example directories
    ├── scripts/            ← reference scripts (validation, simulation)
    ├── api/                ← OpenAPI specification
    └── LIVE-TEST/          ← interactive demo suite
```

## Contact

- Project lead: Roen Branham · roen@smarttasks.cloud
- Technical support: support@iaiso.org
- Enterprise: enterprise@iaiso.org
- Security: security@iaiso.org
