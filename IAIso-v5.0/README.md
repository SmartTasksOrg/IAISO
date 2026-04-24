# IAIso

Bounded-execution primitives and design materials for governing LLM agents.

This repository has two parts:

- **[`core/`](core/)** — the working Python framework with tests, a normative
  specification, and a conformance test suite. This is what you install and
  run. Current version: **0.2.0**.
- **[`vision/`](vision/)** — the larger IAIso **5.0** design framing: the
  pressure-control model, layer model, coin-pusher analogy, solution-pack
  concept, and aspirational SDK/integration catalog. This is design material
  and roadmap, **not shippable code**. Treat it as the long-term direction
  the core is evolving toward.

If you want to use IAIso today, go to [`core/`](core/).
If you want to understand the bigger picture the core is implementing piece
by piece, go to [`vision/`](vision/).

## Quick start

```bash
cd core
pip install -e .
python -m iaiso.conformance spec/   # run the conformance suite
pytest -q                            # 240 passing tests
```

Minimal usage:

```python
from iaiso import BoundedExecution, PressureConfig

with BoundedExecution.start(config=PressureConfig()) as exec:
    outcome = exec.record_tool_call(name="search", tokens=500)
    if outcome.name == "ESCALATED":
        # pause and request human review
        ...
```

See [`core/README.md`](core/README.md) for the full feature list and
[`core/docs/CONFORMANCE.md`](core/docs/CONFORMANCE.md) for the porting guide
to other languages.

## What each zone is for

### `core/` — the shipped implementation

A Python package that actually does what its tests and specification say it
does. Current scope:

- Pressure engine with deterministic math and 20 conformance vectors.
- Consent tokens (HS256 / RS256 JWTs) with 23 conformance vectors.
- Audit envelope with JSON Schema and 7 event-stream vectors.
- Policy-as-code loader with JSON Schema and 17 vectors.
- Middleware for Anthropic, OpenAI, LangChain, LiteLLM, Gemini, Bedrock,
  Mistral, Cohere.
- Audit sinks for stdout, JSONL, Splunk, Datadog, Elastic, Loki, Sumo
  Logic, New Relic, webhook.
- In-memory + Redis-backed cross-execution coordinator.
- Prometheus metrics, OTel tracing.
- Docker, Helm, Terraform deployment templates.
- Admin CLI.
- 240 tests passing (170 unit + 67 conformance + 3 structural).

Everything in `core/` is claim-backed: if the README says it works, there
is a test that proves it. If you find a gap, it's a bug.

### `vision/` — the design frame, roadmap, and future targets

The material from the original IAIso 5.0 README: the pressure-control
philosophy, the 7-layer model, the 5 core invariants, the coin-pusher
mental model, the solution-pack concept, and the catalog of platform
integrations, language SDKs, and compliance frameworks the project aims
to cover over time.

Treat this zone as:

- **Design documentation.** The conceptual layers and invariants the core
  implements are described here.
- **Roadmap.** Platform integrations and language ports that aren't in
  `core/` yet are what future work is aimed at.
- **Historical record.** The repository started from this vision; the core
  is the part that has so far been grounded in working code.

**`vision/` is not installable.** There are intentionally no
`pyproject.toml`, `package.json`, or equivalent files there. Code examples
inside `vision/` are pedagogical sketches, not production implementations.
When a vision concept graduates to working code, it moves into `core/`
(with tests, a spec section, and conformance vectors) and the vision
entry updates to reference it.

## Graduation process

When something in `vision/` is ready to become real:

1. Implement it in `core/` with tests and, where applicable, a
   `spec/<subsystem>/` entry with conformance vectors.
2. Run the existing 240-test suite — it must still pass.
3. Update `core/README.md` and `core/CHANGELOG.md`.
4. Update the corresponding `vision/` section to link to the core
   implementation and mark the vision entry as "shipped."
5. If it changes a wire format or public contract, bump `core/spec/VERSION`
   accordingly (MINOR for additive, MAJOR for breaking).

## Honest status

Not in `core/` yet, present as intent in `vision/`:

- **Layer 0 hardware enforcement.** Requires kernel/hypervisor work; a
  Python library cannot enforce at the BIOS level. Any real Layer 0 path
  will be a separate sidecar or kernel module, not a Python import.
- **Language SDKs beyond Python.** Node, Go, Rust, Java, C#, PHP are
  described as design targets. The conformance harness in
  `core/spec/` is the porting contract; none of the ports themselves
  exist yet.
- **Platform plugins** (Shopify, Salesforce, Meta, WordPress, etc.).
  These are aspirational. None are currently implemented.
- **Compliance certifications** (SOC 2, FedRAMP, HIPAA, etc.).
  Certifications are audit outcomes for deployed systems, not library
  features. `core/` emits audit events that may help operators meet
  compliance requirements, but the library itself cannot be certified.
- **Industry "solution packs."** The concept is described in `vision/`;
  no packs are shipping.

This list is maintained deliberately. Moving something off it requires
code, tests, and (where relevant) spec entries.

## Contributing

- Bug fixes and new tests in `core/` are welcome.
- Moving items from `vision/` to `core/` is the most valuable contribution
  — see "Graduation process" above.
- Pure-vision edits (roadmap refinements, new design docs) belong in
  `vision/` and don't change shipped behavior.
- New concepts with no implementation path should start in `vision/`.

## License

See [`LICENSE`](LICENSE).

## Layout

```
IAISO/
├── README.md                  # This file
├── NOTICE.md                  # Explains the core/vision split to newcomers
├── MIGRATION.md               # How the old 5.0 layout maps into this one
├── LICENSE
├── core/                      # ← shipped code, 0.2.0
│   ├── iaiso/                 #   Python package
│   ├── spec/                  #   Normative specification + conformance vectors
│   ├── tests/                 #   240 tests
│   ├── docs/
│   ├── bench/
│   ├── evals/
│   ├── deploy/
│   ├── pyproject.toml
│   ├── README.md
│   └── CHANGELOG.md
└── vision/                    # ← design + roadmap, not installable
    ├── NOTICE.md              #   Warns this zone is not code
    ├── README.md              #   Original 5.0 README, preserved
    ├── sdk/                   #   Language-SDK sketches (examples only)
    ├── plugins/               #   Platform-integration sketches
    ├── systems/               #   Infrastructure-integration sketches
    ├── config/
    ├── scripts/               #   Deployment-script sketches
    └── docs/                  #   Design & architecture docs
```
