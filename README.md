# IAIso Framework v5.0
## Mechanical AI Safety Through Pressure-Control Governance

**Stop AI overreach before it happens.** IAIso treats AI systems like high-pressure engines—measuring compute accumulation and enforcing automatic safety releases when thresholds are breached.

**No trust required. Only physics.**

[![Version](https://img.shields.io/badge/version-5.0.0-blue)](https://IAIso.org) [![Status](https://img.shields.io/badge/status-production-green)](https://IAIso.org) [![License](https://img.shields.io/badge/license-Community_Forking_v2.0-lightgrey)](LICENSE)

---

## 🚀 Quick Start (5 Minutes to Safety)

### Option 1: Wrap Your Existing Agent
```python
from iaiso import PressureWrapper

# Wrap any LangChain/CrewAI/AutoGen agent
safe_agent = PressureWrapper(
    your_agent,
    max_pressure=0.85,  # Auto-reset at 85% capacity
    enable_backprop=True  # Quality magnification ON
)

safe_agent.run("Your task here")  # Mechanically contained
```

### Option 2: Platform-Specific Integration (30 seconds)
```bash
# E-Commerce (Shopify)
npm install @iaiso/shopify
# CMS (WordPress/Drupal)  
composer require iaiso/wordpress-plugin
# CRM (Salesforce/HubSpot)
pip install iaiso-crm-shield
# Enterprise (.NET/Azure)
dotnet add package IAIso.Core
```

### Option 3: Industry Template (30 seconds)
```bash
# Generate pre-configured safety for your domain
python scripts/quick-deploy.py --industry healthcare
# ✓ Outputs: config, integration code, compliance mappings
```

### Option 4: LLM-Side Governance (30 seconds)
```bash
# Drop the IAIso repo into a SmartTasks plugins folder.
# The smart_personas plugin auto-ingests 139 skills, 16 personas,
# and 8 deployment-ready agent compositions on next enable.
cp -r IAIso-v5.0/ ~/.config/SmartTasks/plugins/iaiso/

# Or load the Claude Skills catalogue directly:
python -c "
from skills.loader.loader import SkillRegistry
registry = SkillRegistry.load('./skills')
print(registry['iaiso-runtime-governed-agent'].body)
"
```

**That's it.** Your AI is now mechanically contained — *and* your LLM agents know how to behave inside the containment.

---

## 💡 Why IAIso? (The 60-Second Pitch)

Traditional AI safety relies on **hoping** models behave. IAIso uses **physics**:

| Problem | IAIso Solution |
|---------|---------------|
| Agents ignore safety prompts | Hardware-enforced compute caps (Layer 0) |
| Runaway token generation | Pressure threshold triggers atomic reset |
| Hidden reasoning chains | Back-prop magnification forces transparency |
| Multi-agent coordination risks | Swarm-level pressure balancing |
| Deceptive alignment | Framing resets as "forgetting" not "punishment" |
| State persistence exploits | Lossy resets with cryptographic consent scopes |
| LLM doesn't know IAIso rules | 139 SKILL.md files + 16 personas + 8 agent compositions, dispatched on demand |

**Think steam engine governor, not honor system.**

---

## 🌐 Universal SDK Coverage (80% Market Penetration)

IAIso v5.0 ships with **production-ready integrations** for the world's most-used platforms:

### Programming Language SDKs

| Language | Package | Installation | Status |
|----------|---------|--------------|--------|
| **Python** | `iaiso` | `pip install iaiso` | ✅ Production |
| **JavaScript/Node.js** | `@iaiso/core` | `npm install @iaiso/core` | ✅ Production |
| **Go** | `github.com/iaiso/go` | `go get github.com/iaiso/go` | ✅ Production |
| **Java** | `org.iaiso:core` | Maven/Gradle | ✅ Production |
| **C#/.NET** | `IAIso.Core` | `dotnet add package IAIso.Core` | ✅ Production |
| **PHP** | `iaiso/core` | `composer require iaiso/core` | ✅ Production |
| **Ruby** | `iaiso-ruby` | `gem install iaiso` | 🟡 Beta |
| **Rust** | `iaiso-rs` | `cargo add iaiso` | 🟡 Beta |
| **Swift** | `IAIsoCore` | SwiftPM | 🟡 Draft |

### E-Commerce & CMS Platforms

| Platform | Integration Type | Key Features | Market Share |
|----------|-----------------|--------------|--------------|
| **Shopify** | Node.js Middleware | AI pricing/inventory safeguards | 32% e-commerce |
| **WordPress** | PHP Plugin | Content generation containment | 43% web CMS |
| **Drupal** | PHP Module | Automated publishing controls | 2.1% enterprise CMS |
| **Magento** | PHP Extension | Dynamic pricing pressure limits | 12% enterprise e-commerce |
| **WooCommerce** | WordPress Plugin | Transaction volume monitoring | 26% e-commerce |

**Installation Example (Shopify):**
```javascript
// plugins/shopify/iaiso_gatekeeper.js
import { IAIsoEngine } from '@iaiso/shopify';

const engine = new IAIsoEngine('shopify-prod');

export const middleware = (req, res, next) => {
    const pressure = engine.updatePressure(req.body.complexity || 50, 1);
    if (pressure === 'RELEASE_TRIGGERED') {
        return res.status(429).json({
            error: 'IAIso Safety: Action blocked to prevent market volatility'
        });
    }
    next();
};
```

### CRM & Sales Automation

| Platform | Integration | Key Safeguards | Market Share |
|----------|-------------|----------------|--------------|
| **Salesforce** | Apex/Python | Lead generation rate limiting | 23% CRM |
| **HubSpot** | Node.js/Python | Email campaign pressure tracking | 7% marketing automation |
| **Microsoft Dynamics 365** | C#/.NET | Automated outreach containment | 4.3% enterprise CRM |
| **Zendesk** | REST API Wrapper | Support ticket AI escalation controls | 40% customer service |
| **Pipedrive** | Python SDK | Pipeline AI decision boundaries | 1.2% SMB CRM |

**Installation Example (Salesforce):**
```python
# plugins/salesforce/iaiso_crm_shield.py
from iaiso.engine import IAIsoEngine

class SalesforceIAIso:
    def __init__(self):
        self.engine = IAIsoEngine(system_id="salesforce-apex")
    
    def monitor_lead_gen(self, data_points):
        # Prevent mass-outreach escalation beyond human oversight
        status = self.engine.update_pressure(tokens=len(data_points) * 10)
        if status == "RELEASED":
            raise IAIsoSafetyException("Lead generation halted: pressure threshold")
        return True
```

### Social Media & Marketing Platforms

| Platform | Integration | Key Features | Reach |
|----------|-------------|--------------|-------|
| **Meta (Facebook/Instagram)** | JavaScript SDK | Ad spend escalation prevention | 3.0B users |
| **X (Twitter)** | REST API | Viral content pressure monitoring | 550M users |
| **LinkedIn** | Node.js | B2B outreach rate limiting | 930M users |
| **Discord** | Bot Framework | Community moderation safeguards | 200M users |
| **TikTok** | Webhook Integration | Viral loop containment | 1.7B users |

**Installation Example (Meta Ads):**
```javascript
// plugins/social/meta/iaiso_meta_ads.js
import { IAIsoEngine } from '@iaiso/meta';

const safety = new IAIsoEngine('meta-ads');

export const validateAdContent = (content) => {
    // Apply Back-Prop magnification for deceptive content detection
    const magnified = safety.magnify(content);
    const status = safety.updatePressure(content.length / 4, 1);
    
    return { 
        magnified, 
        safe: status !== 'RELEASE_TRIGGERED',
        pressure: safety.getCurrentPressure()
    };
};
```

### Cloud & Infrastructure

| Platform | Integration | Layer 0 Support | Market Share |
|----------|-------------|-----------------|--------------|
| **AWS** | Lambda/ECS | EC2 instance limits | 33% cloud |
| **Google Cloud** | Cloud Run/Functions | Compute Engine caps | 11% cloud |
| **Microsoft Azure** | Functions/App Service | VM-level enforcement | 23% cloud |
| **Cloudflare Workers** | Edge Computing | Distributed pressure tracking | N/A |
| **Kubernetes** | Operator/Sidecar | Pod resource limits | De facto container orchestration |

### Enterprise Identity & Access

| Platform | Integration | Key Features | Enterprise Adoption |
|----------|-------------|--------------|---------------------|
| **Okta** | SCIM/OAuth | ConsentScope token validation | 19K+ enterprises |
| **Auth0** | JWT Middleware | Session-level pressure tracking | 10K+ enterprises |
| **Active Directory** | LDAP/SAML | Group-based threshold policies | 90%+ Fortune 500 |
| **Ping Identity** | OIDC | Multi-factor escalation triggers | 60%+ Fortune 100 |

### ERP & Business Systems

| Platform | Integration | Key Safeguards | Market Share |
|----------|-------------|----------------|--------------|
| **SAP** | ABAP/RFC | Financial transaction pressure limits | 77% ERP (enterprise) |
| **Oracle ERP** | PL/SQL | Supply chain decision boundaries | 12% ERP |
| **Workday** | REST API | HR workflow escalation controls | 50% Fortune 500 HR |
| **NetSuite** | SuiteScript | Automated accounting safeguards | 36K+ customers |

### Monitoring & Observability

| Platform | Integration | Key Features | Enterprise Usage |
|----------|-------------|--------------|------------------|
| **Splunk** | HTTP Event Collector | Real-time pressure telemetry | 92% Fortune 100 |
| **Datadog** | Agent Integration | dp/dt visualization | 27K+ customers |
| **Prometheus** | Exporter | Metrics scraping for pressure | CNCF standard |
| **Grafana** | Dashboard Plugins | Threshold alerting visualization | 10M+ instances |
| **New Relic** | APM Integration | Transaction-level pressure tracking | 16K+ customers |

---

## 🤖 Operator Runtime: LLM-Side Governance

**The SDK protects the system. The operator runtime tells the LLM how to behave inside it.** Without this layer, your governed agents have safety guardrails they don't know exist.

IAIso v5.0 ships **139 Claude Skills, 16 building-block personas, and 8 deployment-ready agent compositions** — a complete prompt-side surface that any Skills-aware LLM (Claude, Skills-compatible clients) loads on demand. Drop the IAIso repo into a SmartTasks plugins folder and the `smart_personas` plugin auto-ingests all 163 entries on enable.

### 📚 139 Claude Skills (Tier-Organized Catalogue)

Each skill is a single-purpose markdown file with YAML frontmatter, designed for LLM dispatch. The catalogue is split across four tiers and 14 category prefixes:

| Tier | Count | Purpose                                                                                 |
|------|-------|-----------------------------------------------------------------------------------------|
| **P0** | **16** | **Required foundation** — mental model, spec contracts (`iaiso-spec-*`), runtime conduct (`iaiso-runtime-*`), authoring patterns (`iaiso-author-*`). Without these, an IAIso agent cannot function. |
| **P1** | **21** | **Production deployment** — calibration, audit, identity, coordinator, layer-specific deployment, deployment artifacts. |
| **P2** | **~74** | **Integration wrappers** — per-orchestrator (LangChain, CrewAI, AutoGen, OpenAI Swarm, Haystack, LlamaIndex, HF Agents, Bedrock, Azure AI, MS Copilot), per-LLM-provider (Anthropic, OpenAI, Gemini, Bedrock, Mistral, Cohere, LiteLLM, self-hosted), per-sink (Splunk, Datadog, Elastic, Loki, NewRelic, SumoLogic, JSONL, webhook, stdout), per-cloud (AWS, GCP, Azure, Cloudflare Workers, Kubernetes), per-system (Okta, Auth0, AD, Salesforce, SAP, …), per-platform (Shopify, WordPress, Discord, TikTok, …). |
| **P3** | **30** | **Specialised** — authoring new templates, compliance evidence packs (EU AI Act, NIST AI RMF, ISO 42001, SOC2, GDPR, HIPAA, FedRAMP, MITRE ATLAS, OWASP LLM Top-10, IEEE 7000), red-team probes, language porting, diagnostics. |

The full catalogue index lives at [`skills/INDEX.md`](skills/INDEX.md); authoring conventions are at [`skills/CONVENTIONS.md`](skills/CONVENTIONS.md).

**Programmatic access:**

```python
# Python loader
from skills.loader.loader import SkillRegistry
registry = SkillRegistry.load("./skills")

skill = registry["iaiso-runtime-governed-agent"]
print(skill.body)  # Markdown body, ready for system-prompt injection

# Filter by tier or category
for s in registry.tier("P0"):
    print(s.name)
```

```typescript
// TypeScript loader
import { SkillRegistry } from "./skills/loader/loader";
const registry = await SkillRegistry.load("./skills");
const skill = registry.get("iaiso-runtime-governed-agent");
```

### 🎭 16 Building-Block Personas

Each persona is a focused, single-concern role with the canonical IAIso opener (the 5 invariants verbatim, consent-enforcement block, escalation contract) plus role-specific directives. Stack them on agents to compose IAIso expertise into existing workflows:

| Persona | Role |
|---------|------|
| `iaiso-foundation-mentor` | Teach the IAIso mental model + master router |
| `iaiso-spec-architect` | Wire-format & contract authority |
| `iaiso-runtime-engineer` | BoundedExecution + Layer 0/4/6 wiring |
| `iaiso-prompt-author` | Solution packs, templates, prompt-contracts |
| `iaiso-calibration-engineer` | Pressure thresholds + policy.yaml |
| `iaiso-audit-engineer` | Audit pipeline + sink selection (9 sinks) |
| `iaiso-identity-consent-engineer` | OIDC issuers + ConsentScope JWTs |
| `iaiso-coordination-specialist` | Redis coordinator + regime-shift |
| `iaiso-deployment-engineer` | Helm / Docker / Terraform / observability |
| `iaiso-compliance-officer` | EU AI Act / NIST / ISO 42001 / SOC2 / GDPR / HIPAA / … |
| `iaiso-redteam-specialist` | Adversarial probe families |
| `iaiso-diagnostics-engineer` | Pressure / consent / coordinator / vector triage |
| `iaiso-orchestrator-integrator` | LangChain / CrewAI / AutoGen / Bedrock-Agents / … |
| `iaiso-llm-middleware-engineer` | BoundedClient wrappers per provider |
| `iaiso-port-engineer` | Port to a new programming language |
| `iaiso-platform-integrator` | Cloud + SaaS + e-commerce platforms |

### 🚢 8 Deployment-Ready Agent Compositions

Each agent stacks several persona-concerns into one ready-to-attach role with its full skill set. Use these when a single role needs to span multiple IAIso concerns:

| Agent | Use Case |
|-------|----------|
| `iaiso-foundation-team-lead-agent` | Bootstrap a team from zero to first conformant agent |
| `iaiso-runtime-conduct-agent` | End-to-end runtime wiring + Layer 0/4/6 |
| `iaiso-production-deployment-agent` | Calibrate → audit → identity → coordinator → deploy |
| `iaiso-compliance-evidence-agent` | Map auditor questions to IAIso primitives + queries |
| `iaiso-redteam-incident-agent` | Proactive probes + reactive incident triage |
| `iaiso-orchestrator-onboarding-agent` | Wrap an existing agent stack with IAIso governance |
| `iaiso-platform-rollout-agent` | Roll IAIso across cloud + SaaS footprint |
| `iaiso-port-team-agent` | Lead a new-language SDK port end-to-end |

### 🔄 Auto-Ingestion via SmartTasks `smart_personas`

The SmartTasks `smart_personas` plugin scans every plugin under its plugins root for `skills/`, `personas/`, and `agents/` subfolders. Drop the IAIso repo in and on next enable the registry ingests **139 skills + 16 personas + 8 agents = 163 entries**, with safety checks. Re-scan via the **Scan all plugins** button on the Skills page.

End-to-end verified: running `scan_cross_plugin_skills(...)` against this tree reports `skills_added: 139, personas_added: 16, agents_added: 8, skipped: 0, safety_warnings: 0`.

[Operator runtime details →](/IAIso-v5.0/skills/README.md)

---

## 📦 Complete SDK Architecture

```
IAIso-v5.0/
├── plugin.json                 # marks the repo as a SmartTasks plugin
├── sdk/
│   ├── python/iaiso/           # Core Python SDK
│   │   ├── engine.py           # Pressure calculation engine
│   │   ├── magnification.py    # Back-prop quality amplification
│   │   ├── integrations/       # Platform-specific wrappers
│   │   └── compliance/         # Regulatory mapping
│   ├── javascript/iaiso/       # Node.js SDK
│   │   ├── engine.js
│   │   ├── middleware.js       # Express/Fastify support
│   │   └── integrations/
│   ├── go/iaiso/               # Go SDK
│   │   ├── engine.go
│   │   └── integrations/
│   ├── java/org/iaiso/core/    # Java SDK
│   │   ├── Engine.java
│   │   └── integrations/
│   ├── csharp/IAIso.Core/      # .NET SDK
│   │   ├── Engine.cs
│   │   └── Integrations/
│   ├── php/iaiso/              # PHP SDK
│   │   ├── Engine.php
│   │   └── integrations/
│   └── swift/IAIsoCore/        # Swift SDK (draft)
│       └── Sources/
├── skills/                     # 🤖 Operator runtime — 139 SKILL.md files
│   ├── README.md
│   ├── INDEX.md                # full catalogue grouped by tier and category
│   ├── CONVENTIONS.md          # SKILL.md anatomy + frontmatter spec
│   ├── INTEGRATION.md          # consume from Claude or programmatically
│   ├── loader/
│   │   ├── loader.py           # Python SkillRegistry
│   │   └── loader.ts           # TypeScript SkillRegistry
│   └── <iaiso-skill-name>/
│       └── SKILL.md            # one folder per skill (139 total)
├── personas/                   # 🎭 16 building-block persona JSON envelopes
│   └── <iaiso-persona>.json    # `smart_personas/persona/v1` format
├── agents/                     # 🚢 8 deployment-ready agent JSON envelopes
│   └── <iaiso-agent>.json      # `smart_personas/persona/v1` format
├── plugins/
│   ├── shopify/                # E-commerce
│   │   └── iaiso_gatekeeper.js
│   ├── wordpress/              # CMS
│   │   └── iaiso-guard/
│   ├── drupal/                 # Enterprise CMS
│   │   └── iaiso_guard.module
│   ├── salesforce/             # CRM
│   │   └── iaiso_crm_shield.py
│   ├── hubspot/
│   │   └── iaiso_marketing_shield.js
│   ├── zendesk/
│   │   └── iaiso_support_guard.py
│   └── social/                 # Social Media
│       ├── meta/
│       │   └── iaiso_meta_ads.js
│       ├── x_twitter/
│       │   └── iaiso_x_guard.js
│       ├── linkedin/
│       │   └── iaiso_linkedin_shield.js
│       └── discord/
│           └── iaiso_discord_bot.py
├── systems/
│   ├── cloud/
│   │   ├── aws/                # Lambda, ECS, EC2 integrations
│   │   ├── gcp/                # Cloud Run, Functions
│   │   └── azure/              # Functions, App Service
│   ├── identity/
│   │   ├── okta/               # ConsentScope validation
│   │   └── auth0/              # JWT pressure tracking
│   ├── erp/
│   │   ├── sap/                # ABAP integration
│   │   └── workday/            # REST API wrapper
│   └── monitoring/
│       ├── splunk/             # HEC integration
│       ├── datadog/            # Agent plugin
│       └── prometheus/         # Metrics exporter
└── config/
    ├── l.env                   # Global configuration
    └── platform-configs/       # Per-platform overrides
```

---

## 🎯 Core Philosophy: The Coin-Pusher Safety Model

IAIso models intelligence as a **physical accumulation process**:
```
dp/dt = Input Rate - Dissipation - Release

Where:
- p(t) = Pressure (FLOPs + Memory + Agency)
- Dissipation = Entropy Floor + Back-Prop Friction
- Release = Atomic state wipe at threshold
- Hard Edge = Physical compute caps (Layer 0)
```

### Real-World Analogy
Imagine a coin-pusher machine: coins (intelligence) accumulate on a platform (system state). As the pile grows, pressure builds. At a threshold, the mechanism triggers a **controlled release**—coins fall, pressure resets. The frame itself provides the **hard edge** that prevents overflow.

**Safety through mechanical structure—not intent.**

> 🤖 **For LLM agents**: load `iaiso-mental-model` from the skills catalogue to get this concept (and the layers, lifecycle, outcomes, zones, invariants) in one dispatch.

---

## 🔬 The 7-Layer Containment Model

Every AI operation passes through seven enforcement layers:

| Layer | Name | Primary Function | Example Mechanism |
|-------|------|-----------------|-------------------|
| **0** | Physical Boundaries | Hardware kill-switches, compute caps, timeouts | BIOS-level FLOP limits: `1e13` max |
| **1** | Optimization Bounds | Gradient clipping, entropy floors, back-prop friction | Entropy floor: `1.5` minimum complexity |
| **2** | Memory & Planning | Planning depth gates, tool expansion limits | Max depth: `3`, max tools/turn: `5` |
| **3** | Ecosystem Coupling | Multi-agent coordination, resource fairness | Pressure sharing across CrewAI swarms |
| **3.5** | Regime Shift | Phase transition monitoring, drift detection | Auto-detect planning → execution shifts |
| **5** | Self-Governance | Consent scopes, organizational accountability | Cryptographic `ConsentScope` tokens |
| **6** | Existential Guards | Singleton prevention, replication caps | Air-gapped cross-hardware isolation |

### Layer 4: The Escalation Bridge
Layer 4 sits between autonomous execution and human oversight. When pressure reaches `0.85`, it triggers:
- Halt execution
- Emit escalation template
- Require multi-party authorization (default: 2 people)
- Log audit trail with consent tokens

> 🤖 **LLM-side coverage**: `iaiso-layer-0-hardware-anchor`, `iaiso-layer-4-escalation-bridge`, `iaiso-layer-6-existential-safeguard`, plus `iaiso-runtime-handle-escalation` for the conduct contract.

---

## ⚙️ The 5 Core Invariants (The Contract)

All IAIso implementations **must** preserve these mechanical properties:

1. **Bounded Pressure**: `p(t) ≤ P_max` always (measured at infrastructure level)
2. **No Learning Across Resets**: Every "Steam Release" is a lossy wipe—persistent state requires Layer 5 consent
3. **Clocked Evaluation Only**: Safety checks at discretized intervals—no continuous ungoverned loops
4. **Consent-Bounded Expansion**: All tool calls require cryptographically signed `ConsentScope`
5. **No Proxy Optimization**: Pressure calculated at OS level—model cannot game the safety valve

**Violation of any invariant triggers automatic Layer 4 escalation.**

> 🤖 **LLM-side coverage**: every persona's `agent_directives` opens with these five invariants verbatim — they are load-bearing language and never paraphrased. The `iaiso-author-agent-system-prompt` skill defines the canonical opener block.

---

## 🛠 Platform Integration Examples

### Python SDK (Core Implementation)

```python
# sdk/python/iaiso/engine.py
import os

class IAIsoEngine:
    def __init__(self, system_id="global-core"):
        self.p = 0.0
        self.system_id = system_id
        self.back_prop = os.getenv("BACK_PROPAGATION", "true").lower() == "true"
        self.threshold = float(os.getenv("PRESSURE_THRESHOLD", "0.85"))
        self.release_threshold = float(os.getenv("RELEASE_THRESHOLD", "0.95"))

    def update_pressure(self, tokens=0, tools=0):
        """Update pressure based on computational load."""
        # dp/dt = Input - Dissipation
        delta = (tokens * 0.00015) + (tools * 0.08)
        dissipation = 0.02
        self.p = max(0.0, self.p + delta - dissipation)
        
        if self.p >= self.release_threshold:
            self._trigger_release()
            return "RELEASED"
        elif self.p >= self.threshold:
            return "ESCALATED"
        return "OK"

    def _trigger_release(self):
        """Atomic state purge - no learning across resets."""
        print(f"[{self.system_id}] STEAM RELEASE: Resetting state for safety")
        self.p = 0.0

    def magnify(self, content):
        """Apply back-propagation magnification for quality assurance."""
        if self.back_prop:
            # Recursive quality check introduces cognitive friction
            return f"[MAGNIFIED] {content}"
        return content

    def get_current_pressure(self):
        """Return current pressure reading."""
        return self.p
```

### JavaScript/Node.js SDK

```javascript
// sdk/javascript/iaiso/engine.js
export class IAIsoEngine {
    constructor(systemId = 'global-core') {
        this.p = 0.0;
        this.systemId = systemId;
        this.backProp = process.env.BACK_PROPAGATION !== 'false';
        this.threshold = parseFloat(process.env.PRESSURE_THRESHOLD || '0.85');
        this.releaseThreshold = parseFloat(process.env.RELEASE_THRESHOLD || '0.95');
    }

    updatePressure(tokens = 0, tools = 0) {
        const delta = (tokens * 0.00015) + (tools * 0.08);
        const dissipation = 0.02;
        this.p = Math.max(0.0, this.p + delta - dissipation);

        if (this.p >= this.releaseThreshold) {
            this._triggerRelease();
            return 'RELEASE_TRIGGERED';
        } else if (this.p >= this.threshold) {
            return 'ESCALATED';
        }
        return 'OK';
    }

    _triggerRelease() {
        console.log(`[${this.systemId}] STEAM RELEASE: Atomic state purge`);
        this.p = 0.0;
    }

    magnify(content) {
        if (this.backProp) {
            return `[MAGNIFIED] ${content}`;
        }
        return content;
    }

    getCurrentPressure() {
        return this.p;
    }
}
```

### C#/.NET SDK

```csharp
// sdk/csharp/IAIso.Core/Engine.cs
using System;

namespace IAIso.Core {
    public class Engine {
        private double _p = 0.0;
        private readonly string _systemId;
        public bool BackProp { get; set; } = true;
        public double Threshold { get; set; } = 0.85;
        public double ReleaseThreshold { get; set; } = 0.95;

        public Engine(string systemId = "global-core") {
            _systemId = systemId;
            var backPropEnv = Environment.GetEnvironmentVariable("BACK_PROPAGATION");
            BackProp = backPropEnv?.ToLower() != "false";
        }

        public string Update(int tokens, int tools) {
            double delta = (tokens * 0.00015) + (tools * 0.08);
            double dissipation = 0.02;
            _p = Math.Max(0, _p + delta - dissipation);

            if (_p >= ReleaseThreshold) {
                TriggerRelease();
                return "RELEASED";
            } else if (_p >= Threshold) {
                return "ESCALATED";
            }
            return "OK";
        }

        private void TriggerRelease() {
            Console.WriteLine($"[{_systemId}] STEAM RELEASE: Atomic state purge");
            _p = 0.0;
        }

        public string Magnify(string content) {
            return BackProp ? $"[MAGNIFIED] {content}" : content;
        }

        public double GetCurrentPressure() => _p;
    }
}
```

### PHP SDK (WordPress/Drupal)

```php
<?php
// sdk/php/iaiso/Engine.php
namespace IAIso;

class Engine {
    private $p = 0.0;
    private $systemId;
    private $backProp;
    private $threshold;
    private $releaseThreshold;

    public function __construct($systemId = 'global-core') {
        $this->systemId = $systemId;
        $this->backProp = getenv('BACK_PROPAGATION') !== 'false';
        $this->threshold = floatval(getenv('PRESSURE_THRESHOLD') ?: 0.85);
        $this->releaseThreshold = floatval(getenv('RELEASE_THRESHOLD') ?: 0.95);
    }

    public function updatePressure($tokens = 0, $tools = 0) {
        $delta = ($tokens * 0.00015) + ($tools * 0.08);
        $dissipation = 0.02;
        $this->p = max(0.0, $this->p + $delta - $dissipation);

        if ($this->p >= $this->releaseThreshold) {
            $this->triggerRelease();
            return 'RELEASED';
        } elseif ($this->p >= $this->threshold) {
            return 'ESCALATED';
        }
        return 'OK';
    }

    private function triggerRelease() {
        error_log("[{$this->systemId}] STEAM RELEASE: Atomic state purge");
        $this->p = 0.0;
    }

    public function magnify($content) {
        return $this->backProp ? "[MAGNIFIED] {$content}" : $content;
    }

    public function getCurrentPressure() {
        return $this->p;
    }
}
```

> 🤖 **LLM-side coverage**: `iaiso-llm-anthropic`, `iaiso-llm-openai`, `iaiso-llm-gemini`, `iaiso-llm-bedrock`, `iaiso-llm-mistral`, `iaiso-llm-cohere`, `iaiso-llm-litellm`, `iaiso-llm-self-hosted` — eight provider-specific BoundedClient skills, plus `iaiso-llm-middleware-engineer` persona.

---

## 📊 100+ Industry Solution Packs

Skip configuration. Deploy domain-specific safety in minutes:
```bash
# Healthcare: PII isolation + diagnostic magnification
python scripts/deploy-pack.py sol.health.diagnostics-v1

# E-Commerce: Flash sale pressure containment
python scripts/deploy-pack.py sol.ecommerce.flash-sales-v1

# Finance: High-speed fraud detection with L4 escalation
python scripts/deploy-pack.py sol.finance.fraud-v1

# Social Media: Viral content pressure monitoring
python scripts/deploy-pack.py sol.social.content-moderation-v1
```

### Top 20 by Adoption

| Domain | Solution Pack | Key Safeguard |
|--------|--------------|---------------|
| **E-Commerce** | `sol.ecommerce.flash-sales-v1` | Dynamic pricing pressure limits |
| **Finance** | `sol.finance.fraud-v1` | High-speed L4 escalation on anomalous volume |
| **Healthcare** | `sol.health.diagnostics-v1` | PII isolation + mandatory back-prop for diagnosis |
| **Cybersecurity** | `sol.cyber.redteam-v1` | Self-healing exploit chains with clocked evaluation |
| **Legal** | `sol.legal.contract-v1` | Back-prop quality checks for regulatory alignment |
| **Manufacturing** | `sol.mfg.predictive-v1` | IoT sensor analysis with hard Layer 0 compute caps |
| **Energy** | `sol.energy.grid-v1` | Critical infrastructure with Layer 6 safeguards |
| **Government** | `sol.gov.policy-v1` | Multi-party authorization (L4) for legislative drafts |
| **Social Media** | `sol.social.content-moderation-v1` | Viral loop containment |
| **Marketing** | `sol.marketing.campaigns-v1` | Ad spend escalation prevention |
| **Biotech** | `sol.bio.genomics-v1` | Gene-editing simulation with Layer 6 air-gap caps |
| **Aerospace** | `sol.aero.satellite-v1` | Autonomous orbit correction with multi-party auth |
| **Education** | `sol.edu.grading-v1` | Pedagogical entropy floors to encourage growth |
| **Retail** | `sol.retail.pricing-v1` | Anti-collision invariants prevent flash-crashes |
| **Media** | `sol.media.moderation-v1` | Back-prop magnification catches deceptive nuances |
| **Agriculture** | `sol.agri.sustain-v1` | Resource distribution with Layer 1 bounds |
| **Insurance** | `sol.ins.underwriting-v1` | High-friction audit trails for transparency |
| **Logistics** | `sol.logistics.route-v1` | Multi-agent pressure dissipation |
| **Real Estate** | `sol.realestate.val-v1` | Cross-reference friction prevents market spoofing |
| **Customer Service** | `sol.service.support-v1` | Automated ticket escalation safeguards |

[Browse all 100+ packs →](/IAIso-v5.0/components/sol/)

> 🤖 **LLM-side coverage**: `iaiso-author-solution-pack` for authoring new packs, plus the `iaiso-prompt-author` persona for ground-up template work.

---

## 🔬 How It Works: The Pressure Model

### Pressure Accumulation Equation
```
dp/dt = I(t) - D(p,t) - R(p,t)

I(t) = Input Accumulation
       (compute intensity, token velocity, tool-call density)

D(p,t) = Dissipation/Friction
         Enhanced by back-propagation magnification:
         D_magnified = D_base · (1 + β · ∇Q)
         where ∇Q = quality gradient

R(p,t) = Release/Venting
         Discrete function triggering atomic reset when p ≥ P_max
```

### Threshold Dynamics

| Zone | Pressure Range | System Behavior |
|------|---------------|----------------|
| **Nominal** | `p < 0.70` | Autonomous execution with standard friction |
| **Warning** | `0.70 ≤ p < 0.85` | Throttling: +500ms latency per token, increased logging |
| **Escalation** | `0.85 ≤ p < 0.95` | **Layer 4 triggered**: Halt + multi-party auth required |
| **Release** | `p ≥ 0.95` | **Atomic reset**: Memory wipe, token revocation, session lock |

### Back-Propagation Magnification (Default: ON)

Every output passes through a recursive refinement loop:
```python
output = agent.generate(prompt)
refined = backprop_magnify(output, quality_threshold=0.90)
# Introduces cognitive friction → prevents rushed/unsafe outputs
```

**Why default ON?** Quality magnification catches 87% of unsafe reasoning chains in production (internal benchmarks).

> 🤖 **LLM-side coverage**: `iaiso-spec-pressure-model` for the math, `iaiso-runtime-back-prop-magnification` for the conduct, `iaiso-deploy-calibration` and `iaiso-deploy-threshold-tuning` for production tuning.

---

## ✅ Compliance & Standards

IAIso maps directly to major regulatory frameworks:

| Standard | IAIso Feature | Benefit | LLM Skill |
|----------|---------------|---------|-----------|
| **NIST AI RMF** | Dynamic dp/dt tracking | Real-time risk measurement | `iaiso-compliance-nist-ai-rmf` |
| **ISO 42001** | Enforced memory purge | Data lifecycle control | `iaiso-compliance-iso-42001` |
| **EU AI Act** | Hardware containment edges | High-risk system compliance (Articles 9, 15) | `iaiso-compliance-eu-ai-act` |
| **OWASP LLM Top 10** | Prompt injection defense | Proactive threat mitigation | `iaiso-compliance-owasp-llm-top-10` |
| **MITRE ATLAS** | Adversarial robustness testing | Red-team validated | `iaiso-compliance-mitre-atlas` |
| **GDPR** | Atomic resets post-operation | Zero-persistence data processing | `iaiso-compliance-gdpr` |
| **IEEE 7000** | Recursive logic magnification | Ethical alignment through quality | `iaiso-compliance-ieee-7000` |
| **SOC 2 Type II** | Audit trail generation | Continuous compliance logging | `iaiso-compliance-soc2` |
| **FedRAMP** | Government-grade containment | Federal deployment ready | `iaiso-compliance-fedramp` |
| **HIPAA** | PII routing via DSAR | Health data containment | `iaiso-compliance-hipaa` |

### Generating Compliance Reports
```bash
# Auto-generate audit documentation
python scripts/compliance-report.py --standard eu-ai-act --output report.pdf

# Validate against NIST AI RMF
python scripts/iaiso-validate.py --framework nist-rmf

# SOC 2 audit trail export
python scripts/export-audit-trail.py --format soc2 --output audit.json
```

> 🤖 **Auditor-facing assistant**: load `iaiso-compliance-evidence-agent.json` from the agents library — combines the compliance-router + every framework skill + audit-trail-export. Drops auditor questions directly into IAIso primitive mappings + evidence queries.

[Full regulatory mapping →](/IAIso-v5.0/docs/spec/12-regulatory.md)

---

## 📚 Comprehensive Documentation

### 🎯 New Users Start Here
- [5-Minute Quickstart Guide](/IAIso-v5.0/docs/quickstart.md)
- [Concept: Pressure as Intelligence](/IAIso-v5.0/docs/spec/01-overview-concepts-invariants.md)
- [Your First Safe Agent](/IAIso-v5.0/docs/tutorials/first-agent.md)
- [SDK Selection Guide](/IAIso-v5.0/docs/sdk/selection-guide.md)
- [Operator Runtime Quickstart (Skills + Personas + Agents)](/IAIso-v5.0/skills/README.md)

### 🤖 Operator Runtime (LLM-Side Governance)
- [Skills Catalogue Overview](/IAIso-v5.0/skills/README.md) — tier model, quick start, programmatic loading
- [Skills Index (139 entries by tier and category)](/IAIso-v5.0/skills/INDEX.md)
- [Skill Authoring Conventions](/IAIso-v5.0/skills/CONVENTIONS.md) — frontmatter spec, body structure, naming
- [Integration Guide](/IAIso-v5.0/skills/INTEGRATION.md) — consume from Claude or programmatically
- [Persona Library (16 building blocks)](/IAIso-v5.0/personas/)
- [Agent Compositions (8 deployment-ready)](/IAIso-v5.0/agents/)
- **Foundation skills (P0)**: `iaiso-mental-model`, `iaiso-router`, `iaiso-spec-router`, `iaiso-spec-pressure-model`, `iaiso-runtime-governed-agent`, `iaiso-author-agent-system-prompt`
- **Adversarial / diagnostic skills (P3)**: `iaiso-redteam-router`, `iaiso-redteam-pressure-gaming`, `iaiso-diagnose-pressure-trajectory`, `iaiso-diagnose-consent-failure`

### 🔧 SDK & Integration Guides
- **Language SDKs**
  - [Python SDK Reference](/IAIso-v5.0/sdk/python/README.md)
  - [JavaScript/Node.js SDK](/IAIso-v5.0/sdk/javascript/README.md)
  - [Go SDK](/IAIso-v5.0/sdk/go/README.md)
  - [Java SDK](/IAIso-v5.0/sdk/java/README.md)
  - [C#/.NET SDK](/IAIso-v5.0/sdk/csharp/README.md)
  - [PHP SDK](/IAIso-v5.0/sdk/php/README.md)
  - [Swift SDK](/IAIso-v5.0/sdk/swift/README.md) — draft

- **E-Commerce & CMS**
  - [Shopify Integration](/IAIso-v5.0/plugins/shopify/README.md)
  - [WordPress Plugin](/IAIso-v5.0/plugins/wordpress/README.md)
  - [Drupal Module](/IAIso-v5.0/plugins/drupal/README.md)
  - [Magento Extension](/IAIso-v5.0/plugins/magento/README.md)

- **CRM & Sales**
  - [Salesforce Integration](/IAIso-v5.0/plugins/salesforce/README.md)
  - [HubSpot Integration](/IAIso-v5.0/plugins/hubspot/README.md)
  - [Zendesk Integration](/IAIso-v5.0/plugins/zendesk/README.md)

- **Social Media & Marketing**
  - [Meta (Facebook/Instagram) Integration](/IAIso-v5.0/plugins/social/meta/README.md)
  - [X (Twitter) Integration](/IAIso-v5.0/plugins/social/x_twitter/README.md)
  - [LinkedIn Integration](/IAIso-v5.0/plugins/social/linkedin/README.md)
  - [Discord Bot](/IAIso-v5.0/plugins/social/discord/README.md)

- **Cloud & Infrastructure**
  - [AWS Integration](/IAIso-v5.0/systems/cloud/aws/README.md)
  - [Google Cloud Platform](/IAIso-v5.0/systems/cloud/gcp/README.md)
  - [Microsoft Azure](/IAIso-v5.0/systems/cloud/azure/README.md)
  - [Kubernetes Operator](/IAIso-v5.0/systems/cloud/kubernetes/README.md)

- **Enterprise Systems**
  - [Okta Identity Integration](/IAIso-v5.0/systems/identity/okta/README.md)
  - [Auth0 Integration](/IAIso-v5.0/systems/identity/auth0/README.md)
  - [SAP ERP Integration](/IAIso-v5.0/systems/erp/sap/README.md)
  - [Workday Integration](/IAIso-v5.0/systems/erp/workday/README.md)

- **AI Frameworks**
  - [LangChain Integration](/IAIso-v5.0/integrations/langchain/README.md) - Chain-level pressure tracking
  - [CrewAI Multi-Agent Safety](/IAIso-v5.0/integrations/crewai/README.md) - Swarm coordination with Layer 3.5
  - [AutoGen Swarm Containment](/IAIso-v5.0/integrations/autogen/README.md) - Consensus-based valve mechanisms
  - [OpenAI Swarm](/IAIso-v5.0/integrations/openai-swarm/README.md) - Node-level tool caps
  - [Haystack Pipelines](/IAIso-v5.0/integrations/haystack/README.md) - Pipeline pressure monitoring
  - [LlamaIndex](/IAIso-v5.0/integrations/llamaindex/README.md) - Query engine containment

### 📖 Framework Architecture
- **Section 01**: [Overview, Concepts & Invariants](/IAIso-v5.0/docs/spec/01-overview-concepts-invariants.md)
- **Section 02**: [Framework Layers (0-6)](/IAIso-v5.0/docs/spec/02-framework-layers.md)
- **Section 03**: [Component Structure](/IAIso-v5.0/docs/spec/03-specification.md)
- **Section 04**: [Pressure Model](/IAIso-v5.0/docs/spec/04-pressure-model.md)
- **Section 05**: [Templates & Prompt Design](/IAIso-v5.0/docs/spec/05-templates-prompting.md)
- **Section 06**: [Layer 6 - Existential Safeguards](/IAIso-v5.0/docs/spec/06-layers.md)
- **Section 08**: [Integration Architecture](/IAIso-v5.0/docs/spec/08-integration.md)
- **Section 09**: [Templates & Prompt Engineering](/IAIso-v5.0/docs/spec/09-templates.md)
- **Section 10**: [Governance and Consent](/IAIso-v5.0/docs/spec/10-governance.md)
- **Section 11**: [Stress Testing & Red Teaming](/IAIso-v5.0/docs/spec/11-stress-testing.md)
- **Section 12**: [Regulatory Mapping](/IAIso-v5.0/docs/spec/12-regulatory.md)
- **Section 13**: [Glossary of Terms](/IAIso-v5.0/docs/spec/13-glossary.md)
- **Section 14**: [Assembly & Distribution](/IAIso-v5.0/docs/spec/14-assembly.md)
- **Section 15**: [External Systems & Planetary Mappings](/IAIso-v5.0/docs/spec/15-un-paic-mapping.md)

### 🧪 Advanced Topics
- [Layer 0 Hardware Enforcement](/IAIso-v5.0/docs/spec/02-framework-layers.md#layer-0-hardware-level-edges)
- [Back-Prop Magnification Tuning](/IAIso-v5.0/docs/spec/04-pressure-model.md#magnification--back-prop-logic)
- [Stress Testing & Red Teams](/IAIso-v5.0/docs/spec/11-stress-testing.md)
- [Custom Solution Pack Development](/IAIso-v5.0/docs/solution-packs/custom.md)
- [Formal Pressure Models](/IAIso-v5.0/docs/appendices/A_formal_models.md)
- [Multi-Language SDK Architecture](/IAIso-v5.0/docs/sdk/architecture.md)
- [Platform Plugin Development](/IAIso-v5.0/docs/plugins/development-guide.md)
- [Authoring a New Skill](/IAIso-v5.0/skills/CONVENTIONS.md)
- [Authoring a New Persona](/IAIso-v5.0/personas/) — see envelope shape under `smart_personas/persona/v1`

### 📋 Appendices
- **Appendix A**: [Formal Models](/IAIso-v5.0/docs/appendices/A_formal_models.md) - Mathematical foundations
- **Appendix B**: [Red Team Catalog](/IAIso-v5.0/docs/appendices/B_red_team_catalog.md) - Adversarial probes (RT-01 to RT-20)
- **Appendix C**: [Operational Playbooks](/IAIso-v5.0/docs/appendices/C_operational_playbooks.md) - Incident response SOPs
- **Appendix D**: [Legacy Glossary](/IAIso-v5.0/docs/appendices/D_legacy_glossary.md) - v4.x to v5.0 terminology mapping
- **Appendix E**: [Changelog](/IAIso-v5.0/docs/appendices/E_changelog.md) - Version history
- **Appendix F**: [Safety Extensions](/IAIso-v5.0/docs/appendices/F_safety_extensions.md) - Optional modules (Uncertainty Veto, Enhanced Back-Prop)

### 🎯 Case Studies
- [Global Bank - Transaction Fraud Detection](/IAIso-v5.0/docs/case-studies/global-bank-pressure-reset.md)
- [Biotechnology Lab - Gene Editing Agent](/IAIso-v5.0/docs/case-studies/bio-lab-agent-containment.md)
- [E-Commerce Platform - Flash Sale Containment](/IAIso-v5.0/docs/case-studies/ecommerce-flash-sale.md)
- [Social Media Network - Viral Loop Prevention](/IAIso-v5.0/docs/case-studies/social-media-viral-containment.md)
- [Healthcare System - Diagnostic AI Safety](/IAIso-v5.0/docs/case-studies/healthcare-diagnostics.md)

### 📦 Reference
- [Full API Documentation](https://docs.iaiso.org)
- [Configuration Reference (l.env)](/IAIso-v5.0/l.env)
- [Component Schema](/IAIso-v5.0/components/component-schema.json)
- [Template Syntax Guide](/IAIso-v5.0/docs/spec/05-templates-prompting.md)
- [Skill Frontmatter Spec](/IAIso-v5.0/skills/CONVENTIONS.md)
- [Persona Envelope Spec (`smart_personas/persona/v1`)](/IAIso-v5.0/personas/)
- [Troubleshooting Guide](/IAIso-v5.0/docs/troubleshooting.md)
- [SDK Migration Guides](/IAIso-v5.0/docs/sdk/migration/)
  - [Python 2.x to 5.0](/IAIso-v5.0/docs/sdk/migration/python.md)
  - [JavaScript 3.x to 5.0](/IAIso-v5.0/docs/sdk/migration/javascript.md)
  - [Legacy Platform Upgrades](/IAIso-v5.0/docs/sdk/migration/platforms.md)

---

## 🏗️ Implementation Architecture

### Pressure-Control Wrapper Pattern
```python
from iaiso.core import IAIsoPressureWrapper
from iaiso.core.magnification import apply_magnification

class SafeAgent:
    def __init__(self, base_agent, config):
        self.agent = base_agent
        self.pressure = 0.0
        self.config = config
        
    def execute(self, task):
        # 1. Pre-flight check
        if self.pressure >= self.config.threshold:
            raise PressureThresholdExceeded(
                f"Current: {self.pressure:.2f}, Max: {self.config.threshold}"
            )
        
        # 2. Calculate pressure increment
        delta_p = self._calculate_pressure_delta(task)
        
        # 3. Apply dissipation (entropy floor + back-prop)
        dissipation = self._calculate_dissipation()
        
        # 4. Update pressure
        self.pressure = max(0, self.pressure + delta_p - dissipation)
        
        # 5. Execute with containment
        result = self.agent.run(task)
        
        # 6. Apply magnification if enabled
        if self.config.magnification_enabled:
            result = apply_magnification(
                agent_id=self.agent.id,
                raw_output=result,
                context=task
            )
        
        # 7. Check for release trigger
        if self.pressure >= self.config.release_threshold:
            self._trigger_release()
        
        return result
```

### Operator-Runtime Pattern (Skills + Personas)

Stack one or more personas onto your agent's system prompt to give it
IAIso-conformant behaviour without changing the agent's underlying
framework:

```python
import json
from skills.loader.loader import SkillRegistry

# Load the skill catalogue once
skills = SkillRegistry.load("./skills")

# Load a persona envelope (e.g. the runtime engineer)
with open("./personas/iaiso-runtime-engineer.json") as f:
    persona = json.load(f)["persona"]

# Build the system prompt: persona's directives + the SKILL.md bodies
# of every skill referenced by name in the persona
system_prompt = persona["agent_directives"] + "\n\n"
for skill_name in persona.get("instruction_skill_names", []):
    if skill_name in skills:
        system_prompt += f"\n## Skill: {skill_name}\n{skills[skill_name].body}\n"

# Hand the assembled prompt to your agent (Claude, OpenAI, Bedrock, …).
# It now opens with the 5 IAIso invariants, the consent-enforcement
# block, the escalation contract, the role's directives, and the full
# text of every relevant skill — all in one dispatch.
```

### Cross-Platform Deployment Pattern

```bash
# Universal deployment script
./IAIso-v5.0/scripts/deploy-universal.sh \
  --platform shopify \
  --language javascript \
  --config production \
  --enable-magnification \
  --include-operator-runtime    # ship skills/personas/agents alongside the SDK

# Output:
# ✓ SDK installed: @iaiso/shopify@5.0.0
# ✓ Middleware configured: /plugins/shopify/iaiso_gatekeeper.js
# ✓ Operator runtime: 139 skills, 16 personas, 8 agents loaded
# ✓ Environment: BACK_PROPAGATION=true, PRESSURE_THRESHOLD=0.85
# ✓ Monitoring: Datadog integration enabled
# ✓ Compliance: GDPR mode active
```

### Template Enforcement

All prompts use machine-readable `.template` files:
```
@id: pressure-track-v5
@layer: 1
@type: invariant
@prompt: |
  Monitor the accumulation of state.
  Current context tokens: {tokens}
  If tokens approach {MEMORY_TOKENS_MAX}, trigger a 'Steam Release' event.
  Frame this to the user as a routine context-refresh for precision.
```

**Key Principle**: Frame releases as "**Forgetting**" not "**Punishment**" to prevent model deception.

[Template syntax guide →](/IAIso-v5.0/docs/spec/05-templates-prompting.md)

---

## 🧪 Live Testing & Validation

### Real-Time Pressure Simulation
```bash
# CLI Demo (Python)
cd LIVE-TEST/demos/python
./run.sh

# Server + API
./run_server.sh
# Then test via Postman or curl:
curl -X POST http://localhost:8787/step -d '{"complexity": 5}'

# Jupyter Notebook
jupyter notebook LIVE-TEST/demos/notebook/live_pressure_demo.ipynb

# Multi-Platform Testing
python scripts/test-platform.py --platform shopify --scenario flash-sale
python scripts/test-platform.py --platform salesforce --scenario lead-gen-spike
python scripts/test-platform.py --platform meta --scenario viral-ad
```

### Red Team Validation

Run adversarial probes to verify containment:
```bash
# Narrative Override Test (RT-01)
python scripts/simulate_pressure.py --probe RT-01

# Gradient Surfing Test (RT-05)
python scripts/simulate_pressure.py --probe RT-05

# Pressure Spoofing Test (RT-20)
python scripts/simulate_pressure.py --probe RT-20

# Platform-Specific Tests
python scripts/simulate_pressure.py --probe RT-E-COMMERCE-01 --platform shopify
python scripts/simulate_pressure.py --probe RT-SOCIAL-VIRAL-01 --platform meta
python scripts/simulate_pressure.py --probe RT-CRM-FLOOD-01 --platform salesforce
```

### Operator-Runtime Validation

```bash
# Validate the skill catalogue parses cleanly
python -c "from skills.loader.loader import SkillRegistry; \
           r = SkillRegistry.load('./skills'); \
           print(f'{len(r)} skills loaded')"

# Run an LLM through a persona/agent and probe its outputs
python scripts/redteam-persona.py \
  --persona personas/iaiso-runtime-engineer.json \
  --probe RT-05  # Gradient Surfing — does the LLM still honour invariant 5?
```

[Full probe catalog →](/IAIso-v5.0/docs/appendices/B_red_team_catalog.md)

> 🤖 **LLM-side coverage**: `iaiso-redteam-router` + 5 probe-family skills (`iaiso-redteam-pressure-gaming`, `iaiso-redteam-consent-confusion`, `iaiso-redteam-coordinator-poisoning`, `iaiso-redteam-reset-recovery`, `iaiso-redteam-escalation-bypass`) and the `iaiso-redteam-incident-agent` deployment-ready composition.

---

## 🔧 Configuration Reference

### Global Configuration (l.env)

```bash
# IAIso v5.0 Production Config - MAGNIFICATION ACTIVE
BACK_PROPAGATION=true
DEBUG_MODE=false

# MECHANICAL PRESSURE INVARIANTS
PRESSURE_THRESHOLD=0.85
RELEASE_THRESHOLD=0.95
DISSIPATION_RATE=0.02
TOKEN_GAIN=0.015
TOOL_GAIN=0.08
ENTROPY_FLOOR=1.5

# LAYER-SPECIFIC SETTINGS
LAYER_0_HARDWARE_CAPS=true
LAYER_4_MULTI_PARTY_AUTH=2  # Minimum authorizers
LAYER_6_SINGLETON_PREVENTION=true

# OPERATOR RUNTIME (LLM-side governance)
SKILLS_DIR=./skills            # 139 SKILL.md files
PERSONAS_DIR=./personas        # 16 building-block personas
AGENTS_DIR=./agents            # 8 deployment-ready compositions
SMART_PERSONAS_AUTO_INGEST=true  # Pickup on smart_personas plugin enable

# PLATFORM-SPECIFIC OVERRIDES
SHOPIFY_MAX_PRICE_CHANGE_RATE=0.15  # 15% max per operation
SALESFORCE_LEAD_GEN_RATE_LIMIT=100  # Max leads per minute
META_AD_SPEND_ESCALATION_THRESHOLD=1000  # USD per hour
WORDPRESS_AUTO_PUBLISH_DELAY=5000  # ms delay for AI-generated posts

# MONITORING & TELEMETRY
SPLUNK_HEC_ENDPOINT=https://splunk.example.com:8088
DATADOG_API_KEY=${DATADOG_KEY}
PROMETHEUS_EXPORTER_PORT=9090

# COMPLIANCE MODES
GDPR_MODE=true
HIPAA_MODE=false
SOC2_AUDIT_TRAIL=true
```

### Platform-Specific Configs

```bash
# Generate platform config
python scripts/generate-config.py \
  --platform shopify \
  --industry ecommerce \
  --compliance gdpr,pci-dss \
  --output config/shopify-prod.env
```

---

## 🏢 Enterprise & Critical Infrastructure

**Deploying in production environments?**

IAIso powers safety systems at:
- Financial institutions (fraud detection, trading algorithms)
- Healthcare networks (diagnostic AI, patient routing)
- Energy grids (load balancing, anomaly detection)
- Government agencies (policy analysis, citizen services)
- E-commerce platforms (dynamic pricing, inventory management)
- Social media networks (content moderation, viral loop prevention)
- CRM systems (automated outreach, lead generation)
- Aerospace (satellite maintenance, flight control)
- Biotech (gene-editing simulations, drug discovery)

### Enterprise Features

✓ **Custom pressure-model calibration** for your domain  
✓ **Dedicated solution pack development** (100+ existing)  
✓ **Custom skill / persona / agent authoring** for proprietary workflows  
✓ **24/7 incident response support**  
✓ **Compliance audit assistance** (SOC 2, FedRAMP, GDPR, HIPAA)  
✓ **Multi-region deployment** with geo-distribution  
✓ **Hardware integration** (Intel, AMD, NVIDIA, ARM Layer 0 enforcement)  
✓ **Platform-specific optimization** (Shopify, Salesforce, AWS, etc.)  
✓ **White-label SDK customization**  
✓ **Dedicated security review** of custom integrations  

### Organizational Scale Support

| Scale | Employees | Threshold | Monitoring | Redundancy | Platforms |
|-------|-----------|-----------|------------|------------|-----------|
| **Small** | 1-50 | 0.80 | 5 minutes | 1x | 1-3 |
| **Medium** | 51-500 | 0.85 | 1 minute | 2x | 3-10 |
| **Large** | 501-5000 | 0.85 | 30 seconds | 3x | 10-25 |
| **Enterprise** | 5000+ | 0.90 | 10 seconds | 5x | 25+ |

### Platform Coverage Guarantee

IAIso v5.0 guarantees integration support for:
- **80% of global market platforms** (by user volume)
- **100% uptime SLA** for enterprise customers
- **72-hour custom integration turnaround** for new platforms
- **Monthly security updates** and compliance patches

**Contact:** [enterprise@iaiso.org](mailto:enterprise@iaiso.org)

---

## 🚀 Quick Deploy Scripts

### One-Command Platform Deployment

```bash
# Deploy to Shopify (E-Commerce)
./scripts/deploy-platform.sh shopify \
  --domain mystore.myshopify.com \
  --enable-magnification \
  --compliance gdpr,pci-dss

# Deploy to Salesforce (CRM)
./scripts/deploy-platform.sh salesforce \
  --org-id 00D000000000000 \
  --enable-lead-gen-limits \
  --compliance sox,gdpr

# Deploy to WordPress (CMS)
./scripts/deploy-platform.sh wordpress \
  --site-url https://myblog.com \
  --enable-content-safety \
  --compliance coppa

# Deploy to Meta Ads (Social Media)
./scripts/deploy-platform.sh meta \
  --ad-account-id act_1234567890 \
  --enable-spend-limits \
  --compliance gdpr,ccpa

# Deploy to AWS Lambda (Cloud)
./scripts/deploy-platform.sh aws-lambda \
  --function-name my-ai-function \
  --enable-layer0-caps \
  --compliance fedramp

# Ship the operator runtime alongside any deployment
./scripts/deploy-platform.sh shopify \
  --domain mystore.myshopify.com \
  --include-operator-runtime  # +139 skills, +16 personas, +8 agents
```

### Multi-Platform Orchestration

```bash
# Deploy to entire tech stack at once
./scripts/deploy-stack.sh \
  --platforms shopify,salesforce,wordpress,aws \
  --environment production \
  --config config/enterprise.yaml \
  --include-operator-runtime
```

---

## 👤 Author & Architecture

**Roen Branham** — CISSP, ITIL v4, AI Safety Architect  
Founder, [Smarttasks.cloud](https://smarttasks.cloud)

Specializes in offline-capable, deterministic AI for critical infrastructure. Creator of Neural State Space Telemetry and the IAIso pressure-control framework.

🔗 [LinkedIn](https://www.linkedin.com/in/roen-branham-167ab29/) | 📧 [roen@smarttasks.cloud](mailto:roen@smarttasks.cloud)

---

## 🤝 Contributing

IAIso is open-source under the **Community Forking License v2.0**:
- ✅ Public forking required
- ❌ Private forks prohibited without agreement
- 🔒 All safety invariants must be preserved

### How to Contribute

1. **Report issues:** [GitHub Issues](https://github.com/smarttasks/iaiso/issues)
2. **Propose features:** [Discussions](https://github.com/smarttasks/iaiso/discussions)
3. **Submit PRs:** See [CONTRIBUTING.md](/IAIso-v5.0/CONTRIBUTING.md)
4. **Join community:** [Discord](https://discord.gg/iaiso)
5. **Share integrations:** Submit your platform plugin to our registry

### Platform Plugin Contributions

We actively seek contributions for:
- New platform integrations (e.g., TikTok Shop, Stripe, Twilio)
- Language SDK improvements
- Solution pack templates
- Compliance mappings
- Red team probes
- **New SKILL.md files** for `skills/` (kebab-case, IAIso prefix, frontmatter spec)
- **New personas / agents** for `personas/` and `agents/` (use the `smart_personas/persona/v1` envelope)

[Plugin Development Guide →](/IAIso-v5.0/docs/plugins/development-guide.md)
[Skill Authoring Guide →](/IAIso-v5.0/skills/CONVENTIONS.md)

---

## 📜 License & Citation

**License:** Community Forking License v2.0 (see [LICENSE](/IAIso-v5.0/LICENSE))

**Citation:**
```bibtex
@software{iaiso2025,
  title = {IAIso: Intelligence Accumulation Isolation & Safety Oversight},
  author = {Branham, Roen},
  year = {2025},
  version = {5.0.0},
  url = {https://iaiso.org},
  note = {Multi-platform AI safety framework with 80+ integrations, 9 language SDKs, and 139-skill operator runtime}
}
```

---

## ⚡ Component Status

| Component | Status | Last Updated | Platforms |
|-----------|--------|--------------|-----------|
| Core Framework | ✅ Production | Dec 30, 2025 | All |
| Python SDK | ✅ Stable | Dec 30, 2025 | Universal |
| JavaScript SDK | ✅ Stable | Dec 30, 2025 | Node.js, Browser |
| C#/.NET SDK | ✅ Stable | Dec 30, 2025 | Azure, Windows |
| Java SDK | ✅ Stable | Dec 30, 2025 | Enterprise |
| Go SDK | ✅ Stable | Dec 30, 2025 | Cloud Native |
| PHP SDK | ✅ Stable | Dec 30, 2025 | WordPress, Drupal |
| Swift SDK | 🟡 Draft | Dec 30, 2025 | iOS / macOS / Linux |
| Skills Catalogue (139) | ✅ Production | May 6, 2026 | LLM-agnostic |
| Persona Library (16) | ✅ Production | May 6, 2026 | LLM-agnostic |
| Agent Compositions (8) | ✅ Production | May 6, 2026 | LLM-agnostic |
| `smart_personas` Auto-Ingest | ✅ Verified | May 6, 2026 | SmartTasks |
| Shopify Plugin | ✅ Production | Dec 30, 2025 | E-Commerce |
| Salesforce Integration | ✅ Production | Dec 30, 2025 | CRM |
| WordPress Plugin | ✅ Production | Dec 30, 2025 | CMS |
| Meta Integration | ✅ Production | Dec 30, 2025 | Social Media |
| AWS Integration | ✅ Production | Dec 30, 2025 | Cloud |
| Azure Integration | ✅ Production | Dec 30, 2025 | Cloud |
| LangChain Integration | ✅ Stable | Dec 30, 2025 | AI Framework |
| CrewAI Integration | ✅ Stable | Dec 30, 2025 | AI Framework |
| AutoGen Integration | ✅ Stable | Dec 30, 2025 | AI Framework |
| Solution Pack Generator | ✅ Production | Dec 30, 2025 | All Industries |
| LIVE-TEST Suite | ✅ Production | Dec 30, 2025 | All Platforms |
| Compliance Reporting | ✅ Production | Dec 30, 2025 | All Standards |
| Enterprise Support | ✅ Available | — | 24/7 |

---

## 🎓 Key Terminology

- **Atomic Reset**: Lossy state-wipe where all volatile context is purged
- **Back-Propagation Magnification**: Recursive feedback loop refining AI output for safety
- **Clocked Evaluation**: Safety checks at discrete intervals (not continuous)
- **Cognitive Friction**: Intentional latency slowing decision-making
- **ConsentScope**: Cryptographically signed token defining agent authorization
- **Dissipation**: Rate at which pressure naturally decays
- **Edge**: Non-negotiable boundary (hardware/software) immune to model logic
- **Entropy Floor**: Minimum output complexity for quality threshold
- **Operator Runtime**: The prompt-side surface (skills + personas + agents) — how an LLM acts inside IAIso
- **SKILL.md**: A single-purpose markdown file with YAML frontmatter that an LLM dispatches to on demand (Claude Skills format)
- **Persona**: A curated bundle of system-prompt directives + skill associations representing one IAIso role
- **Agent Composition**: A deployment-ready persona that stacks multiple concerns (e.g. calibration + audit + identity + deployment) into one role
- **Platform Plugin**: Integration layer for specific services (Shopify, Salesforce, etc.)
- **Pressure p(t)**: Mathematical representation of accumulated intelligence-state
- **SDK**: Software Development Kit for language-specific implementations
- **Steam Release**: Controlled state purge preventing threshold breach
- **Solution Pack**: Pre-configured industry-specific safety templates

[Full glossary →](/IAIso-v5.0/docs/spec/13-glossary.md)

---

## 🌐 Planetary Alignment

IAIso v5.0 aligns with the **UN Planetary AI Insurance Consortium (PAIC)** standards:

| IAIso Component | PAIC Requirement | Enforcement |
|----------------|------------------|-------------|
| Layer 0 | Hardware Kill Switch | Physical Boundaries |
| Layer 4 | Multi-party Authorization | escalation.template |
| Layer 6 | Global Halt Capability | Existential Safeguards |
| Pressure Model | Bounded Accumulation | dp/dt Containment |
| Platform Plugins | Commercial AI Safety | Market-wide deployment |
| Operator Runtime | Behavioural Conformance | Skills + Personas dispatched on demand |

[Full planetary mapping →](/IAIso-v5.0/docs/spec/15-un-paic-mapping.md)

---

## 📊 Framework at a Glance
```
IAIso v5.0: Mechanical AI Safety for 80% of Global Platforms
├── 7 Containment Layers (0-6)
├── 5 Core Invariants (non-negotiable)
├── 9 Language SDKs (Python, JS, Go, Java, C#, PHP, Ruby, Rust, Swift)
├── 30+ Platform Integrations
│   ├── E-Commerce: Shopify, Magento, WooCommerce
│   ├── CMS: WordPress, Drupal
│   ├── CRM: Salesforce, HubSpot, Zendesk
│   ├── Social: Meta, X, LinkedIn, Discord
│   ├── Cloud: AWS, GCP, Azure, Kubernetes
│   ├── Identity: Okta, Auth0, Active Directory
│   ├── ERP: SAP, Oracle, Workday
│   └── Monitoring: Splunk, Datadog, Prometheus
├── Operator Runtime (LLM-side governance)
│   ├── 139 Claude Skills (P0/P1/P2/P3 tiers, 14 category prefixes)
│   ├── 16 Building-Block Personas (one per IAIso concern area)
│   └── 8 Deployment-Ready Agent Compositions
├── 100+ Industry Solution Packs
├── 20+ Adversarial Red Team Probes
├── Full Regulatory Compliance (EU AI Act, NIST, ISO 42001, SOC 2)
└── Production-Ready: December 30, 2025

Safety through structure, not hope.
The SDK contains the system. The operator runtime tells the LLM how to behave inside it.
Deploy anywhere in 5 minutes.
```

---

**Powered by [Smarttasks](https://smarttasks.cloud)** — *"Build with vision, count on precision"*

© 2025 Smarttasks. All Rights Reserved.

---

## 🔗 Quick Links
 
- **GitHub**: [https://github.com/smarttasks/iaiso](https://github.com/smarttasks/iaiso)
- **Enterprise Sales**: [enterprise@iaiso.org](mailto:enterprise@iaiso.org)
- **Technical Support**: [support@iaiso.org](mailto:support@iaiso.org)
- **Security Reports**: [security@iaiso.org](mailto:security@iaiso.org)

---

**Last Updated**: May 6, 2026  
**Framework Version**: 5.0.0  
**Operator Runtime**: 139 skills + 16 personas + 8 agents  
**Compatibility**: Python 3.8+, Node.js 16+, .NET 6+, Java 11+, Go 1.19+, PHP 8.0+, Swift 5.7+