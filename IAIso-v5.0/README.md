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

Pick the SDK for your stack. Both target the same spec and produce
interoperable events and tokens.

**Python:**

```bash
cd core/iaiso-python
pip install -e .
python -m iaiso.conformance ../spec/      # 67 conformance vectors
pytest -q                                   # 240 passing tests
```

```python
from iaiso import BoundedExecution, PressureConfig

with BoundedExecution.start(config=PressureConfig()) as execution:
    outcome = execution.record_tool_call(name="search", tokens=500)
    if outcome.name == "ESCALATED":
        # Layer 4: request human review per the escalation template
        ...
```

**Node.js / TypeScript:**

```bash
cd core/iaiso-node
npm install
npm test                                    # 171 tests (104 unit + 67 conformance)
npx iaiso-conformance ./spec                # standalone conformance check
```

```typescript
import { BoundedExecution, PressureConfig } from "@iaiso/core";

await BoundedExecution.run(
  { config: new PressureConfig() },
  async (execution) => {
    const outcome = execution.recordToolCall({ name: "search", tokens: 500 });
    if (outcome === "escalated") {
      // Layer 4: request human review per the escalation template
    }
  },
);
```

**Go:**

```bash
cd core/iaiso-go
go test ./...                              # 48 tests + 67 conformance
go run ./cmd/iaiso-conformance ./spec      # standalone conformance check
```

```go
package main

import (
    "github.com/iaiso/iaiso-go/iaiso/audit"
    "github.com/iaiso/iaiso-go/iaiso/core"
)

func main() {
    sink := audit.NewMemorySink()
    core.Run(core.BoundedExecutionOptions{AuditSink: sink}, func(exec *core.BoundedExecution) error {
        outcome, _ := exec.RecordToolCall("search", 500)
        if outcome == core.StepOutcomeEscalated {
            // Layer 4: request human review per the escalation template
        }
        return nil
    })
}
```

**Rust:**

```bash
cd core/iaiso-rust
cargo test --workspace                         # 47 unit tests + 67 conformance
cargo run -p iaiso-conformance-bin -- ./spec   # standalone conformance check
```

```rust
use iaiso_audit::{MemorySink, Sink};
use iaiso_core::{BoundedExecution, BoundedExecutionOptions, StepOutcome};
use std::sync::Arc;

fn main() {
    let sink: Arc<dyn Sink> = Arc::new(MemorySink::new());
    BoundedExecution::run(
        BoundedExecutionOptions { audit_sink: sink, ..Default::default() },
        |exec| {
            let outcome = exec.record_tool_call("search", 500)?;
            if outcome == StepOutcome::Escalated {
                // Layer 4: request human review per the escalation template
            }
            Ok(())
        },
    ).unwrap();
}
```

**Java:**

```bash
cd core/iaiso-java
./build.sh test                 # 50 unit tests + 67 conformance, no Maven needed
# or with Maven:
mvn clean test
```

```java
import io.iaiso.audit.MemorySink;
import io.iaiso.audit.Sink;
import io.iaiso.core.BoundedExecution;
import io.iaiso.core.BoundedExecutionOptions;
import io.iaiso.core.StepOutcome;

public class Demo {
    public static void main(String[] args) {
        Sink sink = new MemorySink();
        BoundedExecution.run(
            BoundedExecutionOptions.builder().auditSink(sink).build(),
            exec -> {
                StepOutcome outcome = exec.recordToolCall("search", 500);
                if (outcome == StepOutcome.ESCALATED) {
                    // Layer 4: request human review per the escalation template
                }
            });
    }
}
```

**C# / .NET:**

```bash
cd core/iaiso-csharp
dotnet test                                         # build + 50 tests + 67 conformance
dotnet run --project src/Iaiso.Cli -- --help        # admin CLI
```

```csharp
using Iaiso.Audit;
using Iaiso.Core;

var sink = new MemorySink();
BoundedExecution.Run(
    new BoundedExecutionOptions { AuditSink = sink },
    exec =>
    {
        var outcome = exec.RecordToolCall("search", 500);
        if (outcome == StepOutcome.Escalated)
        {
            // Layer 4: request human review per the escalation template
        }
    });
```

**PHP:**

```bash
cd core/iaiso-php
composer install
composer test                                       # 53 unit tests + 67 conformance
./bin/iaiso --help                                  # admin CLI
```

```php
<?php
require 'vendor/autoload.php';

use IAIso\Audit\MemorySink;
use IAIso\Core\BoundedExecution;
use IAIso\Core\BoundedExecutionOptions;
use IAIso\Core\StepOutcome;

$sink = new MemorySink();
BoundedExecution::run(
    new BoundedExecutionOptions(auditSink: $sink),
    function ($exec): void {
        $outcome = $exec->recordToolCall('search', 500);
        if ($outcome === StepOutcome::Escalated) {
            // Layer 4: request human review per the escalation template
        }
    },
);
```

See [`core/README.md`](core/README.md) for the SDK signpost and
[`core/docs/CONFORMANCE.md`](core/docs/CONFORMANCE.md) for the workflow
that ports the framework to additional languages.

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
3. **Implementation** — the runtime lands in `core/iaiso-python/iaiso/` with tests.
   The full suite (`pytest` + `python -m iaiso.conformance core/spec/`)
   must pass.
4. **Release** — `core/iaiso-python/CHANGELOG.md` records the addition;
   `core/spec/VERSION` increments (MINOR for additive, MAJOR for
   breaking) if the contract changed.
5. **Cross-language parity** — language ports land at the top of
   `core/`, alongside the Python SDK: `core/iaiso-python/`,
   `core/iaiso-node/`, future `core/iaiso-go/`, etc. Each SDK is
   self-contained; each re-runs the same conformance vectors in its
   own CI.

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

See [`core/README.md`](core/README.md) for the full list. The Node port
at `@iaiso/core@0.3.0` implements the same capability set: 8 LLM
providers, 8 audit sinks (including the 6 SIEM sinks above), in-memory
and Redis coordinators, Prometheus metrics, OpenTelemetry tracing,
OIDC identity, YAML policies, and an `iaiso` admin CLI. See
[`core/iaiso-node/README.md`](core/iaiso-node/README.md).

## Reference SDKs

| Language | Location | Status | Conformance |
|---|---|---|---|
| Python | [`core/iaiso-python/`](core/iaiso-python/) | Stable · `0.2.0` | 67/67 |
| TypeScript / Node.js | [`core/iaiso-node/`](core/iaiso-node/) | Stable · `@iaiso/core@0.3.0` | 67/67 |
| Go | [`core/iaiso-go/`](core/iaiso-go/) | Stable · `v0.1.0` | 67/67 |
| Rust | [`core/iaiso-rust/`](core/iaiso-rust/) | Stable · `0.1.0` | 67/67 |
| Java | [`core/iaiso-java/`](core/iaiso-java/) | Stable · `0.1.0` | 67/67 |
| C# / .NET | [`core/iaiso-csharp/`](core/iaiso-csharp/) | Stable · `0.1.0` | 67/67 |
| PHP | [`core/iaiso-php/`](core/iaiso-php/) | Stable · `0.1.0` | 67/67 |

All seven implementations target **IAIso spec 1.0** and pass every vector in
[`core/spec/`](core/spec/). They emit identical audit events and produce
interoperable consent tokens for the same inputs. Additional language ports
(Ruby) follow the porting workflow in
[`core/docs/CONFORMANCE.md`](core/docs/CONFORMANCE.md).

## Upcoming from the roadmap

Priorities for subsequent SDK releases include:

- A conformant port into Ruby. Seven reference SDKs (Python, Node, Go,
  Rust, Java, C#, PHP) now serve as worked examples for any future port —
  pick the language whose paradigms map most naturally to your target.
- Additional platform integration patterns graduating from `vision/` to
  `core/`: expanded CRM (Salesforce, HubSpot) adapters, e-commerce
  (Shopify, Magento) adapters, and CMS (WordPress, Drupal) adapters.
- Calibrated default coefficients from published benchmark studies.
- Coordinator gRPC sidecar (the proto is drafted in
  `core/spec/coordinator/wire.proto`).
- Industry solution-pack runtime loader, turning the `vision/`
  solution-pack JSONs into policy files consumable by the SDK.

Follow [`core/iaiso-python/CHANGELOG.md`](core/iaiso-python/CHANGELOG.md) for releases.

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
├── core/                       ← reference SDKs + shared spec (installable per-language)
│   ├── README.md               ← language signpost
│   ├── spec/                   ← normative specification + 67 conformance vectors
│   ├── docs/                   ← language-agnostic framework docs
│   ├── iaiso-python/           ← Python SDK — package `iaiso` (240 tests + 67 vectors)
│   │   ├── iaiso/              ← package source
│   │   ├── tests/
│   │   ├── docs/               ← Python-specific docs
│   │   ├── bench/, evals/, deploy/, examples/, scripts/
│   │   ├── pyproject.toml
│   │   ├── README.md
│   │   └── CHANGELOG.md
│   ├── iaiso-node/             ← Node.js / TypeScript SDK — `@iaiso/core@0.3.0` (171 tests + 67 vectors)
│       ├── src/
│       ├── tests/
│       ├── bin/                ← `iaiso` and `iaiso-conformance` CLIs
│       ├── package.json
│       ├── README.md
│       └── LICENSE
│   ├── iaiso-go/               ← Go SDK — `github.com/iaiso/iaiso-go@v0.1.0` (48 tests + 67 vectors)
│       ├── iaiso/
│       ├── cmd/
│       │   ├── iaiso/          ← admin CLI entry
│       │   └── iaiso-conformance/
│       ├── go.mod
│       ├── README.md
│       └── LICENSE
│   ├── iaiso-rust/             ← Rust SDK — Cargo workspace v0.1.0 (47 tests + 67 vectors)
│       ├── crates/
│       │   ├── core/           ← pressure engine + BoundedExecution
│       │   ├── consent/        ← JWT (HS256/RS256)
│       │   ├── audit/          ← envelope + base sinks
│       │   ├── policy/, coordination/, middleware/, identity/,
│       │   ├── metrics/, observability/, conformance/, cli/
│       ├── cmd/
│       │   ├── iaiso/          ← admin CLI binary
│       │   └── iaiso-conformance/
│       ├── Cargo.toml
│       ├── README.md
│       └── LICENSE
│   ├── iaiso-java/             ← Java SDK — Maven workspace 0.1.0 (50 tests + 67 vectors)
│       ├── iaiso-core/         ← pressure engine + BoundedExecution
│       ├── iaiso-consent/      ← JWT (HS256/RS256, no library deps)
│       ├── iaiso-audit/        ← envelope + base sinks
│       ├── iaiso-policy/, iaiso-coordination/, iaiso-middleware/,
│       ├── iaiso-identity/, iaiso-metrics/, iaiso-observability/,
│       ├── iaiso-conformance/, iaiso-cli/
│       ├── pom.xml             ← parent POM
│       ├── build.sh            ← Maven-free local build
│       ├── README.md
│       └── LICENSE
│   ├── iaiso-csharp/           ← C# / .NET SDK — net8.0 solution 0.1.0 (50 tests + 67 vectors)
│       ├── src/
│       │   ├── Iaiso.Core/     ← pressure engine + BoundedExecution
│       │   ├── Iaiso.Consent/  ← JWT (HS256/RS256, hand-rolled)
│       │   ├── Iaiso.Audit/    ← envelope + base sinks
│       │   ├── Iaiso.Policy/, Iaiso.Coordination/, Iaiso.Middleware/,
│       │   ├── Iaiso.Identity/, Iaiso.Metrics/, Iaiso.Observability/,
│       │   ├── Iaiso.Conformance/, Iaiso.Cli/
│       ├── tests/Iaiso.Tests/  ← in-tree test runner (no xUnit dependency)
│       ├── Iaiso.sln
│       ├── Directory.Build.props
│       ├── README.md
│       └── LICENSE
│   └── iaiso-php/              ← PHP SDK — Composer package 0.1.0 (53 tests + 67 vectors)
│       ├── src/                ← single Composer package, sub-namespaces under IAIso\
│       │   ├── Audit/, Core/, Consent/, Policy/, Coordination/,
│       │   ├── Middleware/{Anthropic,OpenAi,Gemini,Bedrock,Mistral,Cohere,LiteLlm}/,
│       │   ├── Identity/, Metrics/, Observability/, Conformance/, Cli/
│       ├── tests/Unit/, tests/Conformance/  ← PHPUnit
│       ├── bin/iaiso           ← admin CLI launcher
│       ├── composer.json, phpunit.xml
│       ├── README.md
│       └── LICENSE
└── vision/                     ← framework specification
    ├── README.md               ← the IAIso 5.0 design
    ├── docs/                   ← architecture docs (sections 01–15, appendices A–F)
    ├── components/             ← JSON component registry + 100+ solution packs
    ├── templates/              ← prompt templates for solution packs and systems
    ├── integrations/           ← AI framework reference designs
    ├── systems/                ← platform integration reference designs
    ├── examples/               ← industry example directories
    ├── scripts/                ← reference scripts (validation, simulation)
    ├── api/                    ← OpenAPI specification
    └── LIVE-TEST/              ← interactive demo suite
```

## Contact

- Project lead: Roen Branham · roen@smarttasks.cloud
- Technical support: support@iaiso.org
- Enterprise: enterprise@iaiso.org
- Security: security@iaiso.org
