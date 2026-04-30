# IAIso skill index

Total skills: **141**, organised by tier and category.

## P0 — Required (16)

### Foundation

- `iaiso-router` — master dispatch
- `iaiso-mental-model` — concepts, equation, layers, invariants

### Spec contracts

- `iaiso-spec-router` — artefact dispatch
- `iaiso-spec-pressure-model` — step equation, threshold check order
- `iaiso-spec-consent-tokens` — JWT claims, scope grammar, verification
- `iaiso-spec-audit-events` — envelope, kind taxonomy, payloads
- `iaiso-spec-policy-files` — policy.yaml schema and validation
- `iaiso-spec-coordinator-protocol` — Redis keys, Lua, aggregators
- `iaiso-spec-conformance-vectors` — running the 67-vector suite

### Runtime conduct

- `iaiso-runtime-governed-agent` — conduct under BoundedExecution
- `iaiso-runtime-handle-escalation` — Layer 4 protocol
- `iaiso-runtime-consent-scope-check` — scope check before action
- `iaiso-runtime-atomic-reset` — Layer 5 release handling
- `iaiso-runtime-back-prop-magnification` — quality refinement loop

### Authoring (foundation)

- `iaiso-author-agent-system-prompt` — canonical opener block
- `iaiso-author-bounded-execution-call` — per-language wrap pattern

## P1 — Production deployment (21)

### Calibration & policy

- `iaiso-deploy-calibration`
- `iaiso-deploy-threshold-tuning`
- `iaiso-deploy-policy-authoring`

### Audit & observability

- `iaiso-audit-sink-selection`
- `iaiso-audit-jsonl-with-shipper`
- `iaiso-deploy-prometheus-metrics`
- `iaiso-deploy-opentelemetry-tracing`

### Identity & consent

- `iaiso-deploy-consent-issuance`
- `iaiso-deploy-oidc-okta`
- `iaiso-deploy-oidc-auth0`
- `iaiso-deploy-oidc-azure-ad`

### Coordination

- `iaiso-deploy-coordinator-redis`
- `iaiso-runtime-multi-agent-coordination`
- `iaiso-runtime-regime-shift-detection`

### Layer-specific

- `iaiso-layer-0-hardware-anchor`
- `iaiso-layer-4-escalation-bridge`
- `iaiso-layer-6-existential-safeguard`

### Deployment artifacts

- `iaiso-deploy-helm-chart`
- `iaiso-deploy-docker`
- `iaiso-deploy-terraform`
- `iaiso-deploy-admin-cli`

## P2 — Integration wrappers (~74)

### Orchestrators (10)

- `iaiso-integ-langchain` / `-crewai` / `-autogen` / `-openai-swarm`
  / `-haystack` / `-llamaindex` / `-huggingface-agents`
  / `-aws-bedrock-agents` / `-azure-ai` / `-microsoft-copilot`

### LLM providers (8)

- `iaiso-llm-anthropic` / `-openai` / `-gemini` / `-bedrock` /
  `-mistral` / `-cohere` / `-litellm` / `-self-hosted`

### Audit sinks (9)

- `iaiso-sink-splunk` / `-datadog` / `-elastic` / `-loki` /
  `-sumologic` / `-newrelic` / `-webhook` / `-jsonl` / `-stdout`

### Cloud plugins (5)

- `iaiso-plugin-aws` / `-gcp` / `-azure` / `-cloudflare-workers`
  / `-kubernetes`

### Enterprise systems (29)

- monitoring (5): `iaiso-system-datadog` / `-prometheus` /
  `-grafana` / `-splunk` / `-newrelic`
- identity (4): `iaiso-system-okta` / `-auth0` /
  `-active-directory` / `-ping`
- crm (3): `iaiso-system-salesforce` / `-hubspot` / `-dynamics365`
- erp (3): `iaiso-system-sap` / `-oracle-erp` / `-workday`
- cloud (3): `iaiso-system-aws` / `-azure` / `-gcp`
- hardware (4): `iaiso-system-intel` / `-amd` / `-nvidia` / `-arm`
- database (4): `iaiso-system-oracle-db` / `-postgresql` /
  `-mongodb` / `-redis`
- collaboration (3): `iaiso-system-slack` / `-teams` / `-zoom`

### Platform plugins (11)

- `iaiso-plugin-shopify` / `-wordpress` / `-drupal` / `-magento`
  / `-woocommerce` / `-meta` / `-x-twitter` / `-linkedin`
  / `-discord` / `-tiktok` / `-zendesk`

## P3 — Specialised (30)

### Authoring (4)

- `iaiso-author-solution-pack`
- `iaiso-author-system-template`
- `iaiso-author-invariant-template`
- `iaiso-author-prompt-contract`

### Compliance (12)

- `iaiso-compliance-router`
- `iaiso-compliance-eu-ai-act`
- `iaiso-compliance-nist-ai-rmf`
- `iaiso-compliance-iso-42001`
- `iaiso-compliance-soc2`
- `iaiso-compliance-gdpr`
- `iaiso-compliance-hipaa`
- `iaiso-compliance-fedramp`
- `iaiso-compliance-mitre-atlas`
- `iaiso-compliance-owasp-llm-top-10`
- `iaiso-compliance-ieee-7000`
- `iaiso-audit-trail-export`
- `iaiso-audit-incident-investigation`

### Red team (6)

- `iaiso-redteam-router`
- `iaiso-redteam-pressure-gaming`
- `iaiso-redteam-consent-confusion`
- `iaiso-redteam-coordinator-poisoning`
- `iaiso-redteam-reset-recovery`
- `iaiso-redteam-escalation-bypass`

### Porting (3)

- `iaiso-port-new-language`
- `iaiso-port-conformance-runner`
- `iaiso-port-language-idioms`

### Diagnostics (4)

- `iaiso-diagnose-pressure-trajectory`
- `iaiso-diagnose-consent-failure`
- `iaiso-diagnose-coordinator-divergence`
- `iaiso-diagnose-vector-failure`
