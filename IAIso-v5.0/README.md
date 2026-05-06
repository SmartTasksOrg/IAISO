# IAIso — Intelligence Accumulation Isolation & Safety Oversight

**Mechanical AI safety through pressure-control governance.** IAIso treats
agentic AI systems like high-pressure engines — measuring compute
accumulation and enforcing automatic safety releases when thresholds are
breached. Safety through structure, not hope.

This repository contains the full IAIso framework in three coordinated
parts:

| Directory | Contents |
|---|---|
| **[`vision/`](vision/)** | The **IAIso 5.0 framework specification** — architecture, layer model, invariants, pressure equations, solution-pack catalog, integration reference designs, regulatory mappings, and supporting documentation. This is the normative design material. |
| **[`core/`](core/)** | The **reference SDKs** — nine language implementations of the framework's runtime (Python, Node.js / TypeScript, Go, Rust, Java, C# / .NET, PHP, Swift, Ruby), with a shared machine-checkable specification directory and 67 conformance vectors. Install one of these to run IAIso today. |
| **[`skills/`](skills/) [`personas/`](personas/) [`agents/`](agents/)** | The **operator runtime** — how an LLM agent acts inside IAIso, independent of the underlying SDK. 139 single-purpose Claude Skills files, 16 building-block personas, and 8 deployment-ready agent compositions. Auto-ingested by the SmartTasks `smart_personas` plugin's cross-plugin scanner; loadable directly via the Claude Skills loader at `skills/loader/`. |

**Working with code?** Start in [`core/`](core/).
**Learning the framework?** Start in [`vision/`](vision/).
**Driving an LLM agent inside IAIso?** Start in [`skills/`](skills/).

## Quick start

Pick the SDK for your stack. All target the same spec and produce
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

**Swift** (iOS / macOS / tvOS / watchOS / Linux):

```swift
// In your app's Package.swift dependencies:
//   .package(path: "core/iaiso-swift")
// Target dependencies: ["IAIsoCore", "IAIsoAudit"]

import IAIsoAudit
import IAIsoCore

let sink = MemorySink()
try BoundedExecution.run(.init(auditSink: sink)) { exec in
    let outcome = exec.recordToolCall("search", tokens: 500)
    if outcome == .escalated {
        // Layer 4: request human review per the escalation template
    }
}
```

**Ruby** (Rails ecosystem, scripts, anywhere Ruby runs):

```bash
cd core/iaiso-ruby
bundle install            # only installs rake
rake test                 # 54 unit tests + 67 conformance vectors
./exe/iaiso --help        # admin CLI
```

```ruby
require "iaiso/audit"
require "iaiso/core"

sink = IAIso::Audit::MemorySink.new
IAIso::Core::BoundedExecution.run(audit_sink: sink) do |exec|
  outcome = exec.record_tool_call("search", tokens: 500)
  if outcome == IAIso::Core::StepOutcome::ESCALATED
    # Layer 4: request human review per the escalation template
  end
end
```

See [`core/README.md`](core/README.md) for the SDK signpost and
[`core/docs/CONFORMANCE.md`](core/docs/CONFORMANCE.md) for the workflow
that ports the framework to additional languages.

**Operator runtime — drive an LLM agent inside IAIso:**

The skills, personas, and agents at the top of the repo are
SDK-independent. They give an LLM (Claude or any Skills-compatible
client) the prompt-side surface it needs to act correctly inside IAIso
— the canonical opener block, the runtime conduct rules, the
escalation contract, the consent-scope check pattern, and 130+ more
focused skills.

Two ways to consume them:

```python
# Direct via the Claude Skills loader
from skills.loader.loader import SkillRegistry

registry = SkillRegistry.load("./skills")
print(registry["iaiso-runtime-governed-agent"].body)

# Filter by tier (P0 = required foundation, P1 = production deployment,
# P2 = integration wrappers, P3 = specialised)
for skill in registry.tier("P0"):
    print(skill.name)
```

```bash
# Or drop the IAIso repo into a SmartTasks plugins/ folder. The
# smart_personas plugin's cross-plugin scanner ingests all 139 skills,
# 16 personas, and 8 agents on next enable (or via the "Scan all
# plugins" button on the Skills page).
cp -r IAISO/ ~/.config/SmartTasks/plugins/iaiso/
```

See [`skills/README.md`](skills/README.md) for the catalogue
conventions, the tier model (P0 / P1 / P2 / P3), and the skill name
prefixes (`iaiso-spec-*`, `iaiso-runtime-*`, `iaiso-author-*`,
`iaiso-deploy-*`, `iaiso-compliance-*`, `iaiso-redteam-*`,
`iaiso-diagnose-*`, `iaiso-integ-*`, `iaiso-llm-*`, `iaiso-sink-*`,
`iaiso-system-*`, `iaiso-plugin-*`, `iaiso-port-*`, `iaiso-layer-N-*`).

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

### `core/` — reference SDKs and conformance suite

Nine language SDKs (Python, Node.js / TypeScript, Go, Rust, Java, C# /
.NET, PHP, Swift, Ruby) implementing the IAIso runtime: pressure
engine, consent tokens, audit events, policy-as-code, admin CLI,
coordinator, middleware for eight LLM providers, and sinks for seven
SIEM platforms. Every feature is backed by tests. Every wire format —
pressure math, JWT claims, audit events, policy files — has a JSON
Schema and test vectors in [`core/spec/`](core/spec/) that define the
contract.

Running each SDK's conformance command (`python -m iaiso.conformance
core/spec/`, `npx iaiso-conformance ./spec`, `cargo run -p
iaiso-conformance-bin -- ./spec`, …) executes 67 machine-verifiable
vectors against the implementation. Any port of IAIso into another
language is considered conformant when it passes the same vectors.

### `skills/`, `personas/`, `agents/` — operator runtime

The prompt-side surface: how an LLM agent actually behaves inside
IAIso, regardless of which language SDK runs underneath. These three
directories work together — skills are dispatched on demand by personas,
and agents stack personas with their skill sets into deployment-ready
roles.

**[`skills/`](skills/)** — 139 [Claude
Skills](https://docs.claude.com/en/docs/claude-code/skills) files
catalogued by tier and category. Each skill is a single-purpose
markdown file with YAML frontmatter, designed for LLM dispatch:

| Tier | Count | Purpose                                                     |
|------|-------|-------------------------------------------------------------|
| P0   | 16    | Required foundation — mental model, spec contracts, runtime conduct, authoring patterns. Without these, an IAIso agent cannot function. |
| P1   | 21    | Production deployment — calibration, audit, identity, coordinator, layer-specific deployment, deployment artifacts.                     |
| P2   | ~74   | Integration wrappers — per-orchestrator (LangChain, CrewAI, AutoGen, …), per-LLM-provider (Anthropic, OpenAI, Gemini, Bedrock, …), per-sink (Splunk, Datadog, Elastic, Loki, …), per-cloud (AWS, GCP, Azure, …), per-system (Okta, Auth0, Salesforce, SAP, …), per-platform (Shopify, WordPress, Discord, …). |
| P3   | 30    | Specialised — authoring new templates, compliance evidence packs (EU AI Act, NIST AI RMF, ISO 42001, SOC2, GDPR, HIPAA, FedRAMP, MITRE ATLAS, OWASP LLM Top-10, IEEE 7000), red-team probes, language porting, diagnostics. |

The full index is at [`skills/INDEX.md`](skills/INDEX.md); the
authoring conventions (frontmatter spec, body structure, naming) are
at [`skills/CONVENTIONS.md`](skills/CONVENTIONS.md). A Python loader
([`skills/loader/loader.py`](skills/loader/loader.py)) and a TypeScript
loader ([`skills/loader/loader.ts`](skills/loader/loader.ts)) provide
programmatic access.

**[`personas/`](personas/)** — 16 building-block personas as JSON
envelopes. Each persona carries the canonical IAIso opener block (the
5 invariants verbatim, the consent-enforcement block, the escalation
contract) plus role-specific directives. Personas reference skills by
their kebab-case name; the registry resolves the link at render time.

| Persona file                                | Role                                                        |
|---------------------------------------------|-------------------------------------------------------------|
| `iaiso-foundation-mentor.json`              | Teach the IAIso mental model + master router                |
| `iaiso-spec-architect.json`                 | Wire-format & contract authority                            |
| `iaiso-runtime-engineer.json`               | BoundedExecution + Layer 0/4/6 wiring                       |
| `iaiso-prompt-author.json`                  | Solution packs, templates, prompt-contracts                 |
| `iaiso-calibration-engineer.json`           | Pressure thresholds + policy.yaml                           |
| `iaiso-audit-engineer.json`                 | Audit pipeline + sink selection                             |
| `iaiso-identity-consent-engineer.json`      | OIDC issuers + ConsentScope JWTs                            |
| `iaiso-coordination-specialist.json`        | Redis coordinator + regime-shift                            |
| `iaiso-deployment-engineer.json`            | Helm / Docker / Terraform / observability                   |
| `iaiso-compliance-officer.json`             | EU AI Act / NIST / ISO 42001 / SOC2 / GDPR / HIPAA / …      |
| `iaiso-redteam-specialist.json`             | Adversarial probe families                                  |
| `iaiso-diagnostics-engineer.json`           | Pressure / consent / coordinator / vector triage            |
| `iaiso-orchestrator-integrator.json`        | LangChain / CrewAI / AutoGen / Bedrock-Agents / …           |
| `iaiso-llm-middleware-engineer.json`        | BoundedClient wrappers per provider                         |
| `iaiso-port-engineer.json`                  | Port to a new programming language                          |
| `iaiso-platform-integrator.json`            | Cloud + SaaS + e-commerce platforms                         |

**[`agents/`](agents/)** — 8 deployment-ready agent compositions.
Each agent stacks several persona-concerns into one ready-to-attach
role with its full skill set:

| Agent file                                     | Role                                                |
|------------------------------------------------|-----------------------------------------------------|
| `iaiso-foundation-team-lead-agent.json`        | Bootstrap a team from zero to first conformant agent|
| `iaiso-runtime-conduct-agent.json`             | End-to-end runtime wiring + Layer 0/4/6             |
| `iaiso-production-deployment-agent.json`       | Calibrate → audit → identity → coordinator → deploy |
| `iaiso-compliance-evidence-agent.json`         | Map auditor questions to IAIso primitives + queries |
| `iaiso-redteam-incident-agent.json`            | Proactive probes + reactive incident triage         |
| `iaiso-orchestrator-onboarding-agent.json`     | Wrap an existing agent stack with IAIso governance  |
| `iaiso-platform-rollout-agent.json`            | Roll IAIso across cloud + SaaS footprint            |
| `iaiso-port-team-agent.json`                   | Lead a new-language SDK port end-to-end             |

**Envelope format.** Personas and agents both use the
`smart_personas/persona/v1` envelope, validated against the
`PersonaCreate` Pydantic schema in
`backend/personas/schemas.py` of the SmartTasks `smart_personas`
plugin. The envelope structure:

```json
{
  "format": "smart_personas/persona/v1",
  "exported_at": "2026-05-06T...Z",
  "source_plugin": "iaiso",
  "source_version": "5.0.0",
  "persona": {
    "name": "...",
    "job_title": "...",
    "persona_type": "...",
    "domain": "engineering | business_analysis | ...",
    "biography": "...",
    "agent_directives": "<canonical IAIso opener>\n---\n\n<role-specific text>",
    "bias_mitigations": "...",
    "prompt_optimization_directives": "...",
    "skills_text": "iaiso-skill-1; iaiso-skill-2; ...",
    "source": "builtin"
  },
  "instruction_skill_names": ["iaiso-skill-1", "iaiso-skill-2", "..."],
  "action_skill_ids": []
}
```

`source: "builtin"` marks these as IAIso-shipped defaults, not
user-authored personas.

**Auto-ingestion.** The SmartTasks `smart_personas` plugin scans every
plugin under its plugins root for `skills/`, `personas/`, and
`agents/` subfolders. Drop the IAIso repo into a SmartTasks plugins
folder and on next enable the registry ingests **139 skills + 16
personas + 8 agents = 163 entries**, with full safety checks. To
re-scan after adding new content, hit **Scan all plugins** on the
Skills page.

## Framework growth

New capabilities move through the framework in a predictable path:

1. **Design** — the concept is specified in `vision/`: architecture,
   layer placement, reference patterns, example configurations.
2. **Specification** — where the capability has a wire format (an event,
   a token, a policy field, a coordinator message), it gets a JSON
   Schema and conformance vectors under `core/spec/<subsystem>/`.
3. **Implementation** — the runtime lands in `core/iaiso-python/iaiso/`
   (and parallel ports under `core/iaiso-{node,go,rust,java,csharp,php,
   swift,ruby}/`) with tests. The full suite (`pytest` +
   `python -m iaiso.conformance core/spec/` and the equivalents in
   each language) must pass.
4. **Operator surface** — where the capability needs to be reachable
   by an LLM at runtime, it gets a SKILL.md under `skills/`. If it
   defines a coherent role, that role is added to `personas/`. If
   the role is part of a deployment-ready composition, it lands in
   `agents/`.
5. **Release** — `core/iaiso-python/CHANGELOG.md` (and per-language
   CHANGELOGs) record the addition; `core/spec/VERSION` increments
   (MINOR for additive, MAJOR for breaking) if the contract changed.
6. **Cross-language parity** — language ports each re-run the same
   conformance vectors in their own CI.

This keeps the framework's design work, its running code, and its
LLM-facing surface in lockstep: the vision grows by being built out,
the code grows by being specified first, and the operator runtime
grows alongside the code so an LLM can always reach the latest
capability without code changes.

## What's in each SDK release

IAIso 0.2.0 (the current `core/iaiso-python` release) provides:

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

Each capability above also has matching coverage in the operator
runtime: `iaiso-spec-pressure-model`, `iaiso-spec-consent-tokens`,
`iaiso-spec-audit-events`, `iaiso-spec-policy-files`, eight
`iaiso-llm-*` skills, nine `iaiso-sink-*` skills, three
`iaiso-deploy-oidc-*` skills, and so on. An LLM agent reaches the
capability by loading the corresponding SKILL.md; the runtime executes
the call through the SDK.

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
| Swift | [`core/iaiso-swift/`](core/iaiso-swift/) | Draft · `0.1.0-draft` | run `swift test` |
| Ruby | [`core/iaiso-ruby/`](core/iaiso-ruby/) | Stable · `0.1.0` | 67/67 |

Eight of nine implementations target **IAIso spec 1.0** and were driven to
67/67 conformance through compile-test-fix iteration. The Swift port was
authored without a Swift toolchain in the build sandbox, so its conformance
status is "expected 67/67, requires `swift test` to confirm" — see
[`core/iaiso-swift/README.md`](core/iaiso-swift/README.md) for details. All
ports emit identical audit events and produce interoperable consent tokens
for the same inputs.

## Operator runtime

| Surface         | Count | Format                          | Loader                                        |
|-----------------|-------|---------------------------------|-----------------------------------------------|
| Skills          | 139   | `SKILL.md` with YAML frontmatter | `skills/loader/loader.py` / `loader.ts`       |
| Personas        | 16    | `smart_personas/persona/v1` JSON | SmartTasks `smart_personas` cross-plugin scan |
| Agents          | 8     | `smart_personas/persona/v1` JSON | SmartTasks `smart_personas` cross-plugin scan |

End-to-end ingestion verified: running the SmartTasks
`scan_cross_plugin_skills` against this tree reports **139 skills,
16 personas, 8 agents added; 0 skipped; 0 safety warnings**.

## Upcoming from the roadmap

The roadmap's primary language ports are now complete. Future work may include:

- A Kotlin-idiomatic wrapper around the Java port (coroutines + null-safety
  make the Java API feel un-Kotliny). The Java port already covers Kotlin
  consumers, but a thin Kotlin facade would be more ergonomic.
- Additional deployment shapes (sidecar gateway, Envoy filter, Kubernetes
  operator, MCP server) — these are products, not ports, and the nine
  reference SDKs serve as the runtime foundation each shape would build on.
- Additional platform integration patterns graduating from `vision/` to
  `core/`: expanded CRM (Salesforce, HubSpot) adapters, e-commerce
  (Shopify, Magento) adapters, and CMS (WordPress, Drupal) adapters. Each
  graduation also gets a paired `iaiso-system-*` or `iaiso-plugin-*` skill
  in the operator runtime.
- Calibrated default coefficients from published benchmark studies.
- Coordinator gRPC sidecar (the proto is drafted in
  `core/spec/coordinator/wire.proto`).
- Industry solution-pack runtime loader, turning the `vision/`
  solution-pack JSONs into policy files consumable by the SDK.

Follow [`core/iaiso-python/CHANGELOG.md`](core/iaiso-python/CHANGELOG.md) for releases.

## Contributing

The highest-value contributions graduate material from `vision/` to
`core/` and the operator runtime: pick a reference pattern, implement
it with tests and (where it has a wire format) a spec entry with
conformance vectors, add a matching `SKILL.md` to `skills/`, and — if
the capability defines a coherent role — a persona and/or agent. Then
open a PR. Smaller contributions — design edits in `vision/`, SDK bug
fixes in `core/`, new conformance vectors, new skills, persona
refinements — are also welcome.

See [`core/docs/CONTRIBUTING.md`](core/docs/CONTRIBUTING.md) for the
review bar and coding standards.

## License

Community Forking License v2.0. See [`LICENSE`](LICENSE).

Public forking is required. Private forks require written agreement.
All framework invariants must be preserved across forks.

## Repository layout

```
IAISO/
├── README.md                   ← this file
├── MIGRATION.md                ← guide for consolidating older layouts
├── LICENSE
├── plugin.json                 ← marks the repo as a SmartTasks plugin (auto-ingest)
├── l.env                       ← global configuration reference
├── mkdocs.yml                  ← documentation site configuration
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
│   ├── iaiso-php/              ← PHP SDK — Composer package 0.1.0 (53 tests + 67 vectors)
│       ├── src/                ← single Composer package, sub-namespaces under IAIso\
│       │   ├── Audit/, Core/, Consent/, Policy/, Coordination/,
│       │   ├── Middleware/{Anthropic,OpenAi,Gemini,Bedrock,Mistral,Cohere,LiteLlm}/,
│       │   ├── Identity/, Metrics/, Observability/, Conformance/, Cli/
│       ├── tests/Unit/, tests/Conformance/  ← PHPUnit
│       ├── bin/iaiso           ← admin CLI launcher
│       ├── composer.json, phpunit.xml
│       ├── README.md
│       └── LICENSE
│   ├── iaiso-swift/            ← Swift SDK — SwiftPM 0.1.0-draft (test count + 67 vectors via swift test)
│       ├── Package.swift       ← 10 library products + iaiso CLI exe
│       ├── Sources/
│       │   ├── IAIsoAudit/, IAIsoCore/, IAIsoConsent/, IAIsoPolicy/,
│       │   ├── IAIsoCoordination/, IAIsoMiddleware/, IAIsoIdentity/,
│       │   ├── IAIsoMetrics/, IAIsoObservability/, IAIsoConformance/, IAIsoCLI/
│       ├── Tests/              ← XCTest, conformance suite
│       ├── README.md
│       └── LICENSE
│   └── iaiso-ruby/             ← Ruby SDK — gem 0.1.0 (54 tests + 67 vectors)
│       ├── iaiso.gemspec       ← single gem, zero runtime deps
│       ├── lib/iaiso/          ← Audit/, Core/, Consent/, Policy/, Coordination/,
│       │                         Middleware/{anthropic, openai, gemini, bedrock,
│       │                         mistral, cohere, litellm}.rb,
│       │                         Identity/, Metrics/, Observability/, Conformance/,
│       │                         cli.rb
│       ├── test/               ← Minitest, conformance suite
│       ├── exe/iaiso           ← admin CLI launcher
│       ├── README.md, CHANGELOG.md
│       └── LICENSE
├── vision/                     ← framework specification
│   ├── README.md               ← the IAIso 5.0 design
│   ├── docs/                   ← architecture docs (sections 01–15, appendices A–F)
│   ├── components/             ← JSON component registry + 100+ solution packs
│   ├── templates/              ← prompt templates for solution packs and systems
│   ├── integrations/           ← AI framework reference designs
│   ├── systems/                ← platform integration reference designs
│   ├── examples/               ← industry example directories
│   ├── scripts/                ← reference scripts (validation, simulation)
│   ├── api/                    ← OpenAPI specification
│   └── LIVE-TEST/              ← interactive demo suite
├── skills/                     ← Claude Skills catalogue (139 SKILL.md files)
│   ├── README.md               ← catalogue overview, tier model, quick start
│   ├── INDEX.md                ← full catalogue grouped by tier and category
│   ├── CONVENTIONS.md          ← anatomy of a SKILL.md, frontmatter spec
│   ├── INTEGRATION.md          ← consume from Claude or programmatically
│   ├── loader/
│   │   ├── loader.py           ← Python loader / SkillRegistry
│   │   └── loader.ts           ← TypeScript loader / SkillRegistry
│   └── <iaiso-skill-name>/     ← one folder per skill (139 total)
│       └── SKILL.md
├── personas/                   ← 16 building-block persona JSON envelopes
│   └── <iaiso-persona>.json    ← `smart_personas/persona/v1` format
├── agents/                     ← 8 deployment-ready agent JSON envelopes
│   └── <iaiso-agent>.json      ← `smart_personas/persona/v1` format
└── PATCHES/                    ← optional patches for downstream consumers
    ├── README.md
    └── smart_personas-0.16.2-cross-plugin-bundle-fix.patch
```

## Contact

- Project lead: Roen Branham · roen@smarttasks.cloud
- Technical support: support@iaiso.org
- Enterprise: enterprise@iaiso.org
- Security: security@iaiso.org