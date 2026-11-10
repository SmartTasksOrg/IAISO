---
name: iaiso-deploy-prometheus-metrics
description: "Use this skill when wiring IAIso metrics into Prometheus / Grafana. Triggers on `iaiso_*` metrics, scrape config, alert rules. Do not use it for OpenTelemetry traces — see `iaiso-deploy-opentelemetry-tracing`."
version: 1.0.0
tier: P1
category: deploy
framework: IAIso v5.0
license: See ../LICENSE
---

# IAIso metrics on Prometheus

## When this applies

The deployment runs Prometheus or a compatible TSDB and you
want IAIso's pressure / step / sink-drop metrics in Grafana.

## Steps To Complete

1. **Enable the metrics endpoint** in your IAIso runtime
   config. The reference SDK exposes `/metrics` on a
   configurable port.

2. **Add the scrape job:**

   ```yaml
   scrape_configs:
     - job_name: 'iaiso'
       static_configs:
         - targets: ['agent-host:9090']
       scrape_interval: 15s
   ```

3. **Know what is exported.** Core series:

   - `iaiso_pressure_current{execution_id="..."}` — gauge
   - `iaiso_step_total{outcome="ok|escalated|released|locked"}`
   - `iaiso_consent_check_total{result="granted|denied|missing"}`
   - `iaiso_sink_dropped_total{sink="..."}`
   - `iaiso_coordinator_aggregate_pressure{coordinator_id="..."}`
   - histograms for step latency, consent verification time

4. **Set baseline alerts:**

   ```yaml
   - alert: IAIsoSinkDropping
     expr: increase(iaiso_sink_dropped_total[5m]) > 0
     for: 1m
     labels: { severity: page }

   - alert: IAIsoSustainedEscalation
     expr: avg_over_time(iaiso_pressure_current[10m]) > 0.85
     for: 5m
     labels: { severity: warning }

   - alert: IAIsoLockedExecution
     expr: increase(iaiso_step_total{outcome="locked"}[5m]) > 0
     for: 0m
     labels: { severity: page }
   ```

5. **Build the Grafana dashboard.** The reference dashboard
   (in `core/iaiso-python/deploy/grafana/`) covers pressure
   trajectory, step-outcome rate, consent-check rate, and
   sink health. Import it before building your own.

## What this skill does NOT cover

- Tracing — see `../iaiso-deploy-opentelemetry-tracing/SKILL.md`.
- SIEM-style log aggregation — see `iaiso-sink-*`.

## References

- `core/iaiso-python/iaiso/metrics/`
- `core/iaiso-python/deploy/grafana/`
