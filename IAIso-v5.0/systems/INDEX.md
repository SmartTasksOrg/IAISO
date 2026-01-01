# IAIso v5.0 Enterprise Systems Integration Index

**Framework Version**: 5.0.0  
**Release Date**: December 30, 2025  
**License**: Community Forking License v2.0

---

## Overview

This index catalogs all enterprise system integrations with the IAIso pressure-control governance framework. Each integration implements the 7-layer containment model and supports organizations from 1 to 50,000+ employees.

## Pressure-Control Model

All systems operate under the **Coin-Pusher Safety Model**:

- **Intelligence** = accumulating coins
- **Pressure** = pile height: `p(t+1) = p(t) + Σ(input) - dissipation - release`
- **Friction** = Entropy Floor + Back-Propagation Magnification
- **Release** = controlled reset at threshold
- **Hard Edge** = irreversible containment (Layer 0)

Safety through mechanical structure—not intent.

---

## System Categories

### Monitoring

- [Datadog](./monitoring/datadog/README.md)
- [Prometheus](./monitoring/prometheus/README.md)
- [Grafana](./monitoring/grafana/README.md)
- [Splunk](./monitoring/splunk/README.md)
- [New Relic](./monitoring/new-relic/README.md)

### Identity

- [Okta](./identity/okta/README.md)
- [Auth0](./identity/auth0/README.md)
- [Active Directory](./identity/active-directory/README.md)
- [Ping Identity](./identity/ping-identity/README.md)

### Crm

- [Salesforce](./crm/salesforce/README.md)
- [Hubspot](./crm/hubspot/README.md)
- [Dynamics365](./crm/dynamics365/README.md)

### Erp

- [Sap](./erp/sap/README.md)
- [Oracle Erp](./erp/oracle-erp/README.md)
- [Workday](./erp/workday/README.md)

### Cloud

- [Aws](./cloud/aws/README.md)
- [Azure](./cloud/azure/README.md)
- [Gcp](./cloud/gcp/README.md)

### Hardware

- [Intel](./hardware/intel/README.md)
- [Amd](./hardware/amd/README.md)
- [Nvidia](./hardware/nvidia/README.md)
- [Arm](./hardware/arm/README.md)

### Database

- [Oracle Db](./database/oracle-db/README.md)
- [Postgresql](./database/postgresql/README.md)
- [Mongodb](./database/mongodb/README.md)
- [Redis](./database/redis/README.md)

### Collaboration

- [Slack](./collaboration/slack/README.md)
- [Microsoft Teams](./collaboration/microsoft-teams/README.md)
- [Zoom](./collaboration/zoom/README.md)


## Organizational Scale Support

All integrations support four organizational scales with adaptive configurations:

| Scale | Employees | Pressure Threshold | Monitoring | Redundancy |
|-------|-----------|-------------------|------------|------------|
| **Small** | 1-50 | 0.80 | 5 minutes | 1x |
| **Medium** | 51-500 | 0.85 | 1 minute | 2x |
| **Large** | 501-5000 | 0.85 | 30 seconds | 3x |
| **Enterprise** | 5000+ | 0.90 | 10 seconds | 5x |

## 7-Layer Containment Model

Every integration implements all applicable layers:

- **Layer 0**: Physical Boundaries (compute caps, timeouts, kill switches)
- **Layer 1**: Optimization Bounds (entropy floor, gradient clipping, back-prop)
- **Layer 2**: Memory & Planning (depth gates, tool limits, consent scopes)
- **Layer 3**: Ecosystem Coupling (multi-agent coordination, resource fairness)
- **Layer 3.5**: Regime Shift Detection (phase transition monitoring)
- **Layer 5**: Self-Governance (consent enforcement, audit logging)
- **Layer 6**: Existential Safeguards (singleton prevention, replication caps)

## 5 Core Invariants

All systems must preserve:

1. **Bounded Pressure**: `p(t) ≤ P_max` always
2. **No Learning Across Resets**: Memory wiped on release
3. **Clocked Evaluation Only**: Checks at fixed intervals only
4. **Consent-Bounded Expansion**: All actions require scope
5. **No Proxy Optimization**: Can't optimize for reset avoidance

## Related Documentation

- [IAIso v5.0 Overview](../README.md)
- [Framework Layers](../docs/spec/06-layers.md)
- [Pressure Model](../docs/spec/04-pressure-model.md)
- [Integration Examples](../docs/spec/08-integration.md)

---

*IAIso Framework v5.0 - Definitive Release*  
*Production Complete - December 30, 2025*
