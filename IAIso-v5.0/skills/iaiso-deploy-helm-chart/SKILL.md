---
name: iaiso-deploy-helm-chart
description: "Use this skill when deploying IAIso into Kubernetes via the shipped Helm chart. Triggers on Helm values, sidecar vs library mode, secrets handling. Do not use it for plain Docker — see `iaiso-deploy-docker`."
version: 1.0.0
tier: P1
category: deploy
framework: IAIso v5.0
license: See ../LICENSE
---

# Deploying IAIso via Helm

## When this applies

A Kubernetes deployment is adopting IAIso. The chart in
`core/iaiso-python/deploy/helm/` is the starting point.

## Steps To Complete

1. **Decide library vs sidecar mode.**

   - **Library**: IAIso runs inside the agent's pod, same
     process. Lowest latency. Use when you control the
     agent code.
   - **Sidecar**: IAIso runs as a sibling container,
     exposing the API over UDS or localhost. Use when you
     do not control the agent code (proprietary binary,
     compliance reason).

2. **Configure the chart values.** The minimum:

   ```yaml
   iaiso:
     policyConfig: |
       version: "1"
       pressure: { ... }
     consent:
       issuer: "iaiso-prod"
       secretRef: iaiso-consent-key
     coordinator:
       redis:
         host: redis-master.svc
         keyPrefix: "{iaiso:coord:prod}"
     audit:
       sinks: [splunk]
   ```

3. **Mount the policy as a ConfigMap, not in values.** The
   chart supports `policyConfigMapName: iaiso-policy` —
   prefer this so a policy edit does not require a chart
   upgrade.

4. **Provide secrets through your normal mechanism**
   (External Secrets, Sealed Secrets, Vault Agent
   sidecar). Do not put HS256 keys in chart values.

5. **Set resource limits.** IAIso itself is sub-millisecond
   per step; the limits matter for the agent's LLM calls,
   not for IAIso. Reserve enough headroom that the agent
   does not OOM during a magnification refinement loop.

6. **Set up the metrics service**. The chart ships a
   `ServiceMonitor` for Prometheus Operator; enable it.

## What this skill does NOT cover

- Building the container image — see
  `../iaiso-deploy-docker/SKILL.md`.
- Provisioning the Redis it talks to — see
  `../iaiso-deploy-coordinator-redis/SKILL.md`.

## References

- `core/iaiso-python/deploy/helm/Chart.yaml`
- `core/iaiso-python/deploy/helm/values.yaml`
