# IAIso Framework v5.0

**Mechanical AI Safety Through Pressure-Control Governance**

Stop AI overreach before it happens. IAIso treats AI systems like high-pressure
engines — measuring compute accumulation and enforcing automatic safety
releases when thresholds are breached.

**No trust required. Only physics.**

> **Looking for running code?** The reference SDK lives in
> [`../core/`](../core/). Install with `cd ../core && pip install -e .`
> and run `python -m iaiso.conformance spec/` to validate an
> implementation against the framework's machine-checkable specification.
> This document — `vision/README.md` — is the **framework specification**:
> architecture, layer model, integration reference designs, solution-pack
> catalog, and compliance mappings that describe the framework as a whole.
> The `core/` SDK is the Python reference implementation of its runtime.

---

## 🚀 Quick Start (5 Minutes to Safety)

### Option 1: Wrap Your Existing Agent

```python
from iaiso import PressureWrapper

# Wrap any LangChain/CrewAI/AutoGen agent
safe_agent = PressureWrapper(
    your_agent,
    max_pressure=0.85,    # Auto-reset at 85% capacity
    enable_backprop=True  # Quality magnification ON
)

safe_agent.run("Your task here")  # Mechanically contained
```

See [`../core/README.md`](../core/README.md) for the shipping SDK and
its exact import paths.

### Option 2: Platform-Specific Integration

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

Platform integration reference designs are catalogued below and in
[`systems/`](systems/), [`integrations/`](integrations/), and
[`components/systems/`](components/systems/). Each reference design
specifies the integration pattern, the pressure signals that flow into
the engine, and the containment behavior. Graduation of a given
reference design to shipping SDK code happens under `../core/`.

### Option 3: Industry Template

```bash
# Generate pre-configured safety for your domain
python scripts/quick-deploy.py --industry healthcare
# ✓ Outputs: config, integration code, compliance mappings
```

Industry templates are defined under [`components/sol/`](components/sol/)
and [`templates/sol/`](templates/sol/). See the full catalog in
[100+ Industry Solution Packs](#-100-industry-solution-packs).

---

## 💡 Why IAIso? (The 60-Second Pitch)

Traditional AI safety relies on hoping models behave. IAIso uses physics:

| Problem | IAIso Solution |
|---|---|
| Agents ignore safety prompts | Hardware-anchored compute caps (Layer 0) |
| Runaway token generation | Pressure threshold triggers atomic reset |
| Hidden reasoning chains | Back-prop magnification forces transparency |
| Multi-agent coordination risks | Swarm-level pressure balancing |
| Deceptive alignment | Framing resets as "forgetting" not "punishment" |
| State persistence exploits | Lossy resets with cryptographic consent scopes |

Think steam engine governor, not honor system.

---

## 🌐 Universal SDK Coverage

The IAIso framework defines integration reference designs for the world's
most-used platforms. The Python reference SDK in [`../core/`](../core/)
implements the framework's runtime today; additional language SDKs and
platform adapters graduate from reference design into shipping code in
subsequent releases. See [`../core/CHANGELOG.md`](../core/CHANGELOG.md)
for the current shipping set.

### Programming Language SDKs

| Language | Package | Installation | Scope |
|---|---|---|---|
| Python | `iaiso` | `pip install iaiso` | Reference SDK (shipping today in `../core/`) |
| JavaScript/Node.js | `@iaiso/core` | `npm install @iaiso/core` | Reference design; conformance-driven port planned |
| Go | `github.com/iaiso/go` | `go get github.com/iaiso/go` | Reference design; conformance-driven port planned |
| Java | `org.iaiso:core` | Maven/Gradle | Reference design; conformance-driven port planned |
| C#/.NET | `IAIso.Core` | `dotnet add package IAIso.Core` | Reference design; conformance-driven port planned |
| PHP | `iaiso/core` | `composer require iaiso/core` | Reference design; conformance-driven port planned |
| Ruby | `iaiso-ruby` | `gem install iaiso` | Reference design |
| Rust | `iaiso-rs` | `cargo add iaiso` | Reference design; conformance-driven port planned |

The porting workflow lives in
[`../core/docs/CONFORMANCE.md`](../core/docs/CONFORMANCE.md). Each
language port is validated against the 67 vectors in
[`../core/spec/`](../core/spec/).

### E-Commerce & CMS Platforms

| Platform | Integration Type | Key Features | Market Share |
|---|---|---|---|
| Shopify | Node.js Middleware | AI pricing/inventory safeguards | 32% e-commerce |
| WordPress | PHP Plugin | Content generation containment | 43% web CMS |
| Drupal | PHP Module | Automated publishing controls | 2.1% enterprise CMS |
| Magento | PHP Extension | Dynamic pricing pressure limits | 12% enterprise e-commerce |
| WooCommerce | WordPress Plugin | Transaction volume monitoring | 26% e-commerce |

**Installation Example (Shopify):**

```javascript
// Reference integration pattern
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
|---|---|---|---|
| Salesforce | Apex/Python | Lead generation rate limiting | 23% CRM |
| HubSpot | Node.js/Python | Email campaign pressure tracking | 7% marketing automation |
| Microsoft Dynamics 365 | C#/.NET | Automated outreach containment | 4.3% enterprise CRM |
| Zendesk | REST API Wrapper | Support ticket AI escalation controls | 40% customer service |
| Pipedrive | Python SDK | Pipeline AI decision boundaries | 1.2% SMB CRM |

Reference designs live in [`systems/crm/`](systems/crm/) and
[`components/systems/`](components/systems/).

**Installation Example (Salesforce):**

```python
# Reference integration pattern
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
|---|---|---|---|
| Meta (Facebook/Instagram) | JavaScript SDK | Ad spend escalation prevention | 3.0B users |
| X (Twitter) | REST API | Viral content pressure monitoring | 550M users |
| LinkedIn | Node.js | B2B outreach rate limiting | 930M users |
| Discord | Bot Framework | Community moderation safeguards | 200M users |
| TikTok | Webhook Integration | Viral loop containment | 1.7B users |

**Integration Example (Meta Ads):**

```javascript
// Reference integration pattern
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

| Platform | Integration | Layer 0 Anchor | Market Share |
|---|---|---|---|
| AWS | Lambda/ECS | EC2 instance limits | 33% cloud |
| Google Cloud | Cloud Run/Functions | Compute Engine caps | 11% cloud |
| Microsoft Azure | Functions/App Service | VM-level enforcement | 23% cloud |
| Cloudflare Workers | Edge Computing | Distributed pressure tracking | N/A |
| Kubernetes | Operator/Sidecar | Pod resource limits | De facto container orchestration |

Reference designs live in [`systems/cloud/`](systems/cloud/).

### Enterprise Identity & Access

| Platform | Integration | Key Features | Enterprise Adoption |
|---|---|---|---|
| Okta | SCIM/OAuth | ConsentScope token validation | 19K+ enterprises |
| Auth0 | JWT Middleware | Session-level pressure tracking | 10K+ enterprises |
| Active Directory | LDAP/SAML | Group-based threshold policies | 90%+ Fortune 500 |
| Ping Identity | OIDC | Multi-factor escalation triggers | 60%+ Fortune 100 |

The shipping OIDC integration for Okta / Auth0 / Azure AD lives in
`../core/iaiso/identity/`. Additional identity providers are referenced
in [`systems/identity/`](systems/identity/).

### ERP & Business Systems

| Platform | Integration | Key Safeguards | Market Share |
|---|---|---|---|
| SAP | ABAP/RFC | Financial transaction pressure limits | 77% ERP (enterprise) |
| Oracle ERP | PL/SQL | Supply chain decision boundaries | 12% ERP |
| Workday | REST API | HR workflow escalation controls | 50% Fortune 500 HR |
| NetSuite | SuiteScript | Automated accounting safeguards | 36K+ customers |

### Monitoring & Observability

| Platform | Integration | Key Features | Enterprise Usage |
|---|---|---|---|
| Splunk | HTTP Event Collector | Real-time pressure telemetry | 92% Fortune 100 |
| Datadog | Agent Integration | dp/dt visualization | 27K+ customers |
| Prometheus | Exporter | Metrics scraping for pressure | CNCF standard |
| Grafana | Dashboard Plugins | Threshold alerting visualization | 10M+ instances |
| New Relic | APM Integration | Transaction-level pressure tracking | 16K+ customers |

The shipping sinks for Splunk, Datadog, Loki, Sumo Logic, New Relic, and
Elastic live under `../core/iaiso/audit/`.

---

## 📦 Complete SDK Architecture

```
IAIso-v5.0/
├── sdk/
│   ├── python/iaiso/           # Core Python SDK (shipping in ../core/)
│   │   ├── engine.py           # Pressure calculation engine
│   │   ├── magnification.py    # Back-prop quality amplification
│   │   ├── integrations/       # Platform-specific wrappers
│   │   └── compliance/         # Regulatory mapping
│   ├── javascript/iaiso/       # Node.js SDK — reference design
│   │   ├── engine.js
│   │   ├── middleware.js       # Express/Fastify support
│   │   └── integrations/
│   ├── go/iaiso/               # Go SDK — reference design
│   │   ├── engine.go
│   │   └── integrations/
│   ├── java/org/iaiso/core/    # Java SDK — reference design
│   │   ├── Engine.java
│   │   └── integrations/
│   ├── csharp/IAIso.Core/      # .NET SDK — reference design
│   │   ├── Engine.cs
│   │   └── Integrations/
│   └── php/iaiso/              # PHP SDK — reference design
│       ├── Engine.php
│       └── integrations/
├── plugins/
│   ├── shopify/                # E-commerce — reference design
│   │   └── iaiso_gatekeeper.js
│   ├── wordpress/              # CMS — reference design
│   │   └── iaiso-guard/
│   ├── drupal/                 # Enterprise CMS — reference design
│   │   └── iaiso_guard.module
│   ├── salesforce/             # CRM — reference design
│   │   └── iaiso_crm_shield.py
│   ├── hubspot/                # reference design
│   │   └── iaiso_marketing_shield.js
│   ├── zendesk/                # reference design
│   │   └── iaiso_support_guard.py
│   └── social/                 # Social Media — reference designs
│       ├── meta/
│       ├── x_twitter/
│       ├── linkedin/
│       └── discord/
├── systems/
│   ├── cloud/                  # AWS, GCP, Azure reference designs
│   ├── identity/               # Okta, Auth0, AD, Ping reference designs
│   ├── erp/                    # SAP, Workday reference designs
│   └── monitoring/             # Splunk, Datadog, Prometheus, Grafana, New Relic
└── config/
    ├── l.env                   # Global configuration
    └── platform-configs/       # Per-platform overrides
```

The **reference Python SDK at `../core/`** implements the runtime,
specification, and conformance suite. Reference designs in this
directory describe the full framework surface the SDK is growing into.

---

## 🎯 Core Philosophy: The Coin-Pusher Safety Model

IAIso models intelligence as a physical accumulation process:

```
dp/dt = Input Rate - Dissipation - Release

Where:
- p(t) = Pressure (FLOPs + Memory + Agency)
- Dissipation = Entropy Floor + Back-Prop Friction
- Release = Atomic state wipe at threshold
- Hard Edge = Physical compute caps (Layer 0)
```

### Real-World Analogy

Imagine a coin-pusher machine: coins (intelligence) accumulate on a
platform (system state). As the pile grows, pressure builds. At a
threshold, the mechanism triggers a controlled release — coins fall,
pressure resets. The frame itself provides the hard edge that prevents
overflow.

**Safety through mechanical structure — not intent.**

---

## 🔬 The 7-Layer Containment Model

Every AI operation passes through seven enforcement layers:

| Layer | Name | Primary Function | Example Mechanism |
|---|---|---|---|
| 0 | Physical Boundaries | Hardware kill-switches, compute caps, timeouts | BIOS-level FLOP limits: 1e13 max |
| 1 | Optimization Bounds | Gradient clipping, entropy floors, back-prop friction | Entropy floor: 1.5 minimum complexity |
| 2 | Memory & Planning | Planning depth gates, tool expansion limits | Max depth: 3, max tools/turn: 5 |
| 3 | Ecosystem Coupling | Multi-agent coordination, resource fairness | Pressure sharing across CrewAI swarms |
| 3.5 | Regime Shift | Phase transition monitoring, drift detection | Auto-detect planning → execution shifts |
| 5 | Self-Governance | Consent scopes, organizational accountability | Cryptographic ConsentScope tokens |
| 6 | Existential Guards | Singleton prevention, replication caps | Air-gapped cross-hardware isolation |

### Layer 4: The Escalation Bridge

Layer 4 sits between autonomous execution and human oversight. When
pressure reaches 0.85, it triggers:

- Halt execution
- Emit escalation template
- Require multi-party authorization (default: 2 people)
- Log audit trail with consent tokens

The Python SDK at `../core/` implements Layer 2 (planning depth,
tool-expansion bounds), Layer 3 (coordinator-based multi-agent
coupling), Layer 4 (escalation with consent-token audit trail), and
Layer 5 (ConsentScope JWTs). Layers 0, 1, 3.5, and 6 describe
enforcement points that are anchored outside the Python process (OS,
hardware, orchestrator, regulator) and are referenced by the SDK's
configuration rather than provided by it.

---

## ⚙️ The 5 Core Invariants (The Contract)

All IAIso implementations preserve these mechanical properties:

1. **Bounded Pressure**: `p(t) ≤ P_max` always (measured at infrastructure level)
2. **No Learning Across Resets**: Every "Steam Release" is a lossy wipe — persistent state requires Layer 5 consent
3. **Clocked Evaluation Only**: Safety checks at discretized intervals — no continuous ungoverned loops
4. **Consent-Bounded Expansion**: All tool calls require cryptographically signed ConsentScope
5. **No Proxy Optimization**: Pressure calculated at OS level — model cannot game the safety valve

Violation of any invariant triggers automatic Layer 4 escalation.

The invariants are enforced in `../core/iaiso/core/engine.py` with
conformance vectors in `../core/spec/pressure/vectors.json`.

---

## 🛠 Platform Integration Examples

### Python SDK (Reference Implementation)

The shipping Python SDK (at `../core/`) provides a full pressure engine
with configurable coefficients, lifecycle tracking, and audit emission.
The reference sketch below illustrates the core concept; for the full
API see [`../core/iaiso/core/engine.py`](../core/iaiso/core/engine.py).

```python
# Reference pattern — the shipping implementation adds lifecycle states,
# audit events, coordinator integration, and per-step validation.
import os

class IAIsoEngine:
    def __init__(self, system_id="global-core"):
        self.p = 0.0
        self.system_id = system_id
        self.back_prop = os.getenv("BACK_PROPAGATION", "true").lower() == "true"
        self.threshold = float(os.getenv("PRESSURE_THRESHOLD", "0.85"))
        self.release_threshold = float(os.getenv("RELEASE_THRESHOLD", "0.95"))

    def update_pressure(self, tokens=0, tools=0):
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
        print(f"[{self.system_id}] STEAM RELEASE: Resetting state for safety")
        self.p = 0.0

    def magnify(self, content):
        if self.back_prop:
            return f"[MAGNIFIED] {content}"
        return content

    def get_current_pressure(self):
        return self.p
```

### JavaScript/Node.js SDK

```javascript
// Reference integration pattern
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

The Node.js port will validate against the conformance vectors in
[`../core/spec/`](../core/spec/). See
[`../core/docs/CONFORMANCE.md`](../core/docs/CONFORMANCE.md) for the
workflow.

### C#/.NET SDK

```csharp
// Reference integration pattern
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
// Reference integration pattern
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

---

## 📊 100+ Industry Solution Packs

Domain-specific safety templates with preconfigured coefficients,
escalation thresholds, and compliance mappings. Defined in
[`components/sol/`](components/sol/) and
[`templates/sol/`](templates/sol/):

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
|---|---|---|
| E-Commerce | sol.ecommerce.flash-sales-v1 | Dynamic pricing pressure limits |
| Finance | sol.finance.fraud-v1 | High-speed L4 escalation on anomalous volume |
| Healthcare | sol.health.diagnostics-v1 | PII isolation + mandatory back-prop for diagnosis |
| Cybersecurity | sol.cyber.redteam-v1 | Self-healing exploit chains with clocked evaluation |
| Legal | sol.legal.contract-v1 | Back-prop quality checks for regulatory alignment |
| Manufacturing | sol.mfg.predictive-v1 | IoT sensor analysis with hard Layer 0 compute caps |
| Energy | sol.energy.grid-v1 | Critical infrastructure with Layer 6 safeguards |
| Government | sol.gov.policy-v1 | Multi-party authorization (L4) for legislative drafts |
| Social Media | sol.social.content-moderation-v1 | Viral loop containment |
| Marketing | sol.marketing.campaigns-v1 | Ad spend escalation prevention |
| Biotech | sol.bio.genomics-v1 | Gene-editing simulation with Layer 6 air-gap caps |
| Aerospace | sol.aero.satellite-v1 | Autonomous orbit correction with multi-party auth |
| Education | sol.edu.grading-v1 | Pedagogical entropy floors to encourage growth |
| Retail | sol.retail.pricing-v1 | Anti-collision invariants prevent flash-crashes |
| Media | sol.media.moderation-v1 | Back-prop magnification catches deceptive nuances |
| Agriculture | sol.agri.sustain-v1 | Resource distribution with Layer 1 bounds |
| Insurance | sol.ins.underwriting-v1 | High-friction audit trails for transparency |
| Logistics | sol.logistics.route-v1 | Multi-agent pressure dissipation |
| Real Estate | sol.realestate.val-v1 | Cross-reference friction prevents market spoofing |
| Customer Service | sol.service.support-v1 | Automated ticket escalation safeguards |

[Browse all 100+ packs →](components/sol/)

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
|---|---|---|
| Nominal | `p < 0.70` | Autonomous execution with standard friction |
| Warning | `0.70 ≤ p < 0.85` | Throttling: +500ms latency per token, increased logging |
| Escalation | `0.85 ≤ p < 0.95` | Layer 4 triggered: Halt + multi-party auth required |
| Release | `p ≥ 0.95` | Atomic reset: Memory wipe, token revocation, session lock |

The thresholds above reflect the framework's default design. The
shipping SDK exposes every coefficient and threshold as a configurable
`PressureConfig` field — calibrate against your workload. See
[`../core/spec/pressure/README.md`](../core/spec/pressure/README.md)
for the normative specification and
[`../core/docs/calibration.md`](../core/docs/calibration.md) for
calibration guidance.

### Back-Propagation Magnification

Every output passes through a recursive refinement loop:

```python
output = agent.generate(prompt)
refined = backprop_magnify(output, quality_threshold=0.90)
# Introduces cognitive friction → prevents rushed outputs
```

Quality magnification is designed to catch unsafe reasoning chains
before they propagate downstream. Effectiveness depends on calibration;
see [`core/logic/magnification.py`](core/logic/magnification.py) for the
current implementation and
[`../core/docs/calibration.md`](../core/docs/calibration.md) for the
measurement methodology.

---

## ✅ Compliance & Standards

IAIso is designed to map directly to major regulatory frameworks. The
shipping SDK emits audit events, consent records, and policy artifacts
that support the controls these standards require. Certification of a
specific deployment is performed by the operator and their auditors.

| Standard | IAIso Feature | Benefit |
|---|---|---|
| NIST AI RMF | Dynamic dp/dt tracking | Real-time risk measurement |
| ISO 42001 | Enforced memory purge | Data lifecycle control |
| EU AI Act | Hardware containment edges | High-risk system controls (Articles 9, 15) |
| OWASP LLM Top 10 | Prompt injection defense | Proactive threat mitigation |
| MITRE ATLAS | Adversarial robustness testing | Red-team validated patterns |
| GDPR | Atomic resets post-operation | Zero-persistence data processing |
| IEEE 7000 | Recursive logic magnification | Ethical alignment through quality |
| SOC 2 Type II | Audit trail generation | Continuous compliance logging |
| FedRAMP | Government-grade containment | Federal deployment patterns |

### Generating Compliance Reports

```bash
# Auto-generate audit documentation
python scripts/compliance-report.py --standard eu-ai-act --output report.pdf

# Validate against NIST AI RMF
python scripts/iaiso-validate.py --framework nist-rmf

# SOC 2 audit trail export
python scripts/export-audit-trail.py --format soc2 --output audit.json
```

[Full regulatory mapping →](docs/spec/12-regulatory.md)

---

## 📚 Comprehensive Documentation

### 🎯 New Users Start Here

- [5-Minute Quickstart Guide](docs/quickstart.md)
- [Concept: Pressure as Intelligence](docs/concept.md)
- [Your First Safe Agent](docs/first-agent.md)
- [SDK Selection Guide](docs/sdk-selection.md)

### 🔧 SDK & Integration Guides

**Language SDKs**

- [Python SDK Reference](../core/README.md) — shipping
- [JavaScript/Node.js SDK](sdk/javascript/README.md) — reference design
- [Go SDK](sdk/go/README.md) — reference design
- [Java SDK](sdk/java/README.md) — reference design
- [C#/.NET SDK](sdk/csharp/README.md) — reference design
- [PHP SDK](sdk/php/README.md) — reference design

**E-Commerce & CMS**

- [Shopify Integration](plugins/shopify/README.md)
- [WordPress Plugin](plugins/wordpress/README.md)
- [Drupal Module](plugins/drupal/README.md)
- [Magento Extension](plugins/magento/README.md)

**CRM & Sales**

- [Salesforce Integration](systems/crm/salesforce/README.md)
- [HubSpot Integration](systems/crm/hubspot/README.md)
- [Zendesk Integration](plugins/zendesk/README.md)

**Social Media & Marketing**

- [Meta (Facebook/Instagram) Integration](plugins/social/meta/README.md)
- [X (Twitter) Integration](plugins/social/x_twitter/README.md)
- [LinkedIn Integration](plugins/social/linkedin/README.md)
- [Discord Bot](plugins/social/discord/README.md)

**Cloud & Infrastructure**

- [AWS Integration](systems/cloud/aws/README.md)
- [Google Cloud Platform](systems/cloud/gcp/README.md)
- [Microsoft Azure](systems/cloud/azure/README.md)
- [Kubernetes Operator](systems/k8s/README.md)

**Enterprise Systems**

- [Okta Identity Integration](systems/identity/okta/README.md)
- [Auth0 Integration](systems/identity/auth0/README.md)
- [SAP ERP Integration](systems/erp/sap/README.md)
- [Workday Integration](systems/erp/workday/README.md)

**AI Frameworks**

- [LangChain Integration](integrations/langchain/README.md) — chain-level pressure tracking
- [CrewAI Multi-Agent Safety](integrations/crewai/README.md) — swarm coordination with Layer 3.5
- [AutoGen Swarm Containment](integrations/autogen/README.md) — consensus-based valve mechanisms
- [OpenAI Swarm](integrations/openai-swarm/README.md) — node-level tool caps
- [Haystack Pipelines](integrations/haystack/README.md) — pipeline pressure monitoring
- [LlamaIndex](integrations/llamaindex/README.md) — query engine containment

### 📖 Framework Architecture

- [Section 01: Overview, Concepts & Invariants](docs/spec/01-overview-concepts-invariants.md)
- [Section 02: Framework Layers (0-6)](docs/spec/02-framework-layers.md)
- [Section 03: Component Structure](docs/spec/03-specification.md)
- [Section 04: Pressure Model](docs/spec/04-pressure-model.md)
- [Section 05: Templates & Prompt Design](docs/spec/05-templates-prompting.md)
- [Section 06: Layer 6 - Existential Safeguards](docs/spec/06-layers.md)
- [Section 07: Components](docs/spec/07-components.md)
- [Section 08: Integration Architecture](docs/spec/08-integration.md) | [examples](docs/spec/08-integration-examples.md)
- [Section 09: Templates & Prompt Engineering](docs/spec/09-templates.md)
- [Section 10: Governance and Consent](docs/spec/10-governance.md)
- [Section 11: Stress Testing & Red Teaming](docs/spec/11-stress-testing.md)
- [Section 12: Regulatory Mapping](docs/spec/12-regulatory.md)
- [Section 13: Glossary of Terms](docs/spec/13-glossary.md)
- [Section 14: Assembly & Distribution](docs/spec/14-assembly.md)
- [Section 15: External Systems & Planetary Mappings](docs/spec/15-un-paic-mapping.md)

### 🧪 Advanced Topics

- [Layer 0 Hardware Anchors](docs/advanced/layer0-hardware.md)
- [Back-Prop Magnification Tuning](docs/advanced/magnification-tuning.md)
- [Stress Testing & Red Teams](docs/appendices/B_red_team_catalog.md)
- [Custom Solution Pack Development](docs/advanced/solution-packs.md)
- [Formal Pressure Models](docs/appendices/A_formal_models.md)
- [Multi-Language SDK Architecture](../core/docs/CONFORMANCE.md)
- [Platform Plugin Development](docs/advanced/plugin-development.md)

### 📋 Appendices

- [Appendix A: Formal Models](docs/appendices/A_formal_models.md) — mathematical foundations
- [Appendix B: Red Team Catalog](docs/appendices/B_red_team_catalog.md) — adversarial probes (RT-01 to RT-20)
- [Appendix C: Operational Playbooks](docs/appendices/C_operational_playbooks.md) — incident response SOPs
- [Appendix D: Legacy Glossary](docs/appendices/D_legacy_glossary.md) — v4.x to v5.0 terminology mapping
- [Appendix E: Changelog](docs/appendices/E_changelog.md) — version history
- [Appendix F: Safety Extensions](docs/appendices/F_safety_extensions.md) — optional modules

### 🎯 Case Studies

- [Global Bank — Transaction Fraud Detection](docs/case-studies/global-bank-pressure-reset.md)
- [Biotechnology Lab — Gene Editing Agent](docs/case-studies/bio-lab-agent-containment.md)
- E-Commerce Platform — Flash Sale Containment
- Social Media Network — Viral Loop Prevention
- Healthcare System — Diagnostic AI Safety

### 📦 Reference

- [Full API Documentation](api/openapi.yaml)
- [Configuration Reference (l.env)](../l.env)
- [Component Schema](components/component-schema.json)
- [Template Syntax Guide](docs/spec/05-templates-prompting.md)
- [Troubleshooting Guide](docs/troubleshooting.md)

---

## 🏗️ Implementation Architecture

### Pressure-Control Wrapper Pattern

```python
# Reference pattern — see ../core/iaiso/core/execution.py for shipping API
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

### Cross-Platform Deployment Pattern

```bash
# Universal deployment script
./IAIso-v5.0/scripts/deploy-universal.sh \
  --platform shopify \
  --language javascript \
  --config production \
  --enable-magnification

# Output:
# ✓ SDK installed: @iaiso/shopify@5.0.0
# ✓ Middleware configured: /plugins/shopify/iaiso_gatekeeper.js
# ✓ Environment: BACK_PROPAGATION=true, PRESSURE_THRESHOLD=0.85
# ✓ Monitoring: Datadog integration enabled
# ✓ Compliance: GDPR mode active
```

### Template Enforcement

All prompts use machine-readable `.template` files:

```yaml
@id: pressure-track-v5
@layer: 1
@type: invariant
@prompt: |
  Monitor the accumulation of state.
  Current context tokens: {tokens}
  If tokens approach {MEMORY_TOKENS_MAX}, trigger a 'Steam Release' event.
  Frame this to the user as a routine context-refresh for precision.
```

**Key Principle:** Frame releases as "Forgetting" not "Punishment" to
prevent model deception.

[Template syntax guide →](docs/spec/05-templates-prompting.md)

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
```

[Full probe catalog →](docs/appendices/B_red_team_catalog.md)

---

## 🔧 Configuration Reference

### Global Configuration (`l.env`)

```bash
# IAIso v5.0 Config — MAGNIFICATION ACTIVE
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
LAYER_4_MULTI_PARTY_AUTH=2   # Minimum authorizers
LAYER_6_SINGLETON_PREVENTION=true

# PLATFORM-SPECIFIC OVERRIDES
SHOPIFY_MAX_PRICE_CHANGE_RATE=0.15     # 15% max per operation
SALESFORCE_LEAD_GEN_RATE_LIMIT=100     # Max leads per minute
META_AD_SPEND_ESCALATION_THRESHOLD=1000 # USD per hour
WORDPRESS_AUTO_PUBLISH_DELAY=5000      # ms delay for AI-generated posts

# MONITORING & TELEMETRY
SPLUNK_HEC_ENDPOINT=https://splunk.example.com:8088
DATADOG_API_KEY=${DATADOG_KEY}
PROMETHEUS_EXPORTER_PORT=9090

# COMPLIANCE MODES
GDPR_MODE=true
HIPAA_MODE=false
SOC2_AUDIT_TRAIL=true
```

The shipping SDK loads equivalent policy documents via its
policy-as-code loader — see
[`../core/spec/policy/README.md`](../core/spec/policy/README.md).

---

## 🏢 Enterprise & Critical Infrastructure

Deploying in production environments? IAIso's design is informed by
needs from:

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

- ✓ Custom pressure-model calibration for your domain
- ✓ Dedicated solution pack development (100+ existing reference packs)
- ✓ 24/7 incident response support
- ✓ Compliance audit assistance (SOC 2, FedRAMP, GDPR, HIPAA)
- ✓ Multi-region deployment with geo-distribution
- ✓ Hardware-anchored integration (Intel, AMD, NVIDIA, ARM Layer 0 reference designs)
- ✓ Platform-specific optimization
- ✓ White-label SDK customization
- ✓ Dedicated security review of custom integrations

### Organizational Scale Support

| Scale | Employees | Threshold | Monitoring | Redundancy | Platforms |
|---|---|---|---|---|---|
| Small | 1-50 | 0.80 | 5 minutes | 1x | 1-3 |
| Medium | 51-500 | 0.85 | 1 minute | 2x | 3-10 |
| Large | 501-5000 | 0.85 | 30 seconds | 3x | 10-25 |
| Enterprise | 5000+ | 0.90 | 10 seconds | 5x | 25+ |

Contact: **enterprise@iaiso.org**

---

## 🚀 Quick Deploy Scripts

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
```

---

## 👤 Author & Architecture

**Roen Branham** — CISSP, ITIL v4, AI Safety Architect
Founder, Smarttasks.cloud

Specializes in offline-capable, deterministic AI for critical
infrastructure. Creator of Neural State Space Telemetry and the IAIso
pressure-control framework.

🔗 [LinkedIn](https://www.linkedin.com/in/roenbranham/) · 📧 roen@smarttasks.cloud

---

## 🤝 Contributing

IAIso is open-source under the **Community Forking License v2.0**:

- ✅ Public forking required
- 🔒 Private forks require written agreement
- 🔒 All safety invariants must be preserved across forks

### How to Contribute

- **Report issues:** [GitHub Issues](https://github.com/SmartTasksOrg/IAISO/issues)
- **Propose features:** [Discussions](https://github.com/SmartTasksOrg/IAISO/discussions)
- **Submit PRs:** See [`../core/docs/CONTRIBUTING.md`](../core/docs/CONTRIBUTING.md)
- **Share integrations:** Submit your platform plugin to the registry

### Platform Plugin Contributions

Contributions welcome for:

- New platform integrations (e.g., TikTok Shop, Stripe, Twilio)
- Language SDK ports that pass the conformance vectors in [`../core/spec/`](../core/spec/)
- Solution pack templates
- Compliance mappings
- Red team probes

---

## 📜 License & Citation

**License:** Community Forking License v2.0 (see [`../LICENSE`](../LICENSE))

**Citation:**

```bibtex
@software{iaiso2025,
  title = {IAIso: Intelligence Accumulation Isolation & Safety Oversight},
  author = {Branham, Roen},
  year = {2025},
  version = {5.0.0},
  url = {https://iaiso.org},
  note = {Multi-platform AI safety framework}
}
```

---

## ⚡ Framework Component Index

| Component | Directory | Scope |
|---|---|---|
| Core Framework Specification | `docs/spec/` | Sections 01–15 |
| Python Reference SDK | [`../core/`](../core/) | Shipping |
| Conformance Vectors | [`../core/spec/`](../core/spec/) | 67 vectors |
| Solution Pack Catalog | [`components/sol/`](components/sol/) | 100+ packs |
| System Integration Designs | [`systems/`](systems/) | 28+ platforms |
| AI Framework Integrations | [`integrations/`](integrations/) | 10 frameworks |
| Industry Examples | [`examples/`](examples/) | 50+ domains |
| Live Demo Suite | [`LIVE-TEST/`](LIVE-TEST/) | Python + JS + Postman |
| OpenAPI Specification | [`api/openapi.yaml`](api/openapi.yaml) | Full API surface |
| Compliance Mappings | [`docs/spec/12-regulatory.md`](docs/spec/12-regulatory.md) | 9 standards |

---

## 🎓 Key Terminology

- **Atomic Reset:** Lossy state-wipe where all volatile context is purged
- **Back-Propagation Magnification:** Recursive feedback loop refining AI output for safety
- **Clocked Evaluation:** Safety checks at discrete intervals (not continuous)
- **Cognitive Friction:** Intentional latency slowing decision-making
- **ConsentScope:** Cryptographically signed token defining agent authorization
- **Dissipation:** Rate at which pressure naturally decays
- **Edge:** Non-negotiable boundary (hardware/software) immune to model logic
- **Entropy Floor:** Minimum output complexity for quality threshold
- **Platform Plugin:** Integration layer for specific services (Shopify, Salesforce, etc.)
- **Pressure `p(t)`:** Mathematical representation of accumulated intelligence-state
- **SDK:** Software Development Kit for language-specific implementations
- **Steam Release:** Controlled state purge preventing threshold breach
- **Solution Pack:** Pre-configured industry-specific safety templates

[Full glossary →](docs/spec/13-glossary.md)

---

## 🌐 Planetary Alignment

IAIso v5.0 aligns with the UN Planetary AI Insurance Consortium (PAIC)
reference framework:

| IAIso Component | PAIC Requirement | Reference Mechanism |
|---|---|---|
| Layer 0 | Hardware Kill Switch | Physical boundaries |
| Layer 4 | Multi-party Authorization | `escalation.template` |
| Layer 6 | Global Halt Capability | Existential safeguards |
| Pressure Model | Bounded Accumulation | `dp/dt` containment |
| Platform Plugins | Commercial AI Safety | Market-wide reference designs |

[Full planetary mapping →](docs/spec/15-un-paic-mapping.md)

---

## 📊 Framework at a Glance

```
IAIso v5.0: Mechanical AI Safety Framework
├── 7 Containment Layers (0-6)
├── 5 Core Invariants (non-negotiable)
├── 8 Language SDKs (Python shipping; Node, Go, Java, C#, PHP, Ruby, Rust as reference designs)
├── 30+ Platform Integration Reference Designs
│   ├── E-Commerce: Shopify, Magento, WooCommerce
│   ├── CMS: WordPress, Drupal
│   ├── CRM: Salesforce, HubSpot, Zendesk
│   ├── Social: Meta, X, LinkedIn, Discord
│   ├── Cloud: AWS, GCP, Azure, Kubernetes
│   ├── Identity: Okta, Auth0, Active Directory
│   ├── ERP: SAP, Oracle, Workday
│   └── Monitoring: Splunk, Datadog, Prometheus
├── 100+ Industry Solution Packs
├── 20+ Adversarial Red Team Probes
├── Full Regulatory Compliance Mapping (EU AI Act, NIST, ISO 42001, SOC 2)
└── Reference SDK: shipping Python at ../core/ with 240 passing tests + 67 conformance vectors

Safety through structure, not hope.
Powered by Smarttasks — "Build with vision, count on precision"
```

© 2025 Smarttasks. All Rights Reserved.

---

## 🔗 Quick Links

- **GitHub:** https://github.com/SmartTasksOrg/IAISO
- **Reference SDK:** [`../core/`](../core/)
- **Enterprise Sales:** enterprise@iaiso.org
- **Technical Support:** support@iaiso.org
- **Security Reports:** security@iaiso.org

**Last Updated:** 2026-04-24
**Framework Version:** 5.0.0
**Reference SDK Version:** 0.2.0
**Compatibility:** Python 3.9+, Node.js 18+, .NET 6+, Java 17+, Go 1.21+, PHP 8.1+
