---
name: iaiso-deploy-opentelemetry-tracing
description: "Use this skill when wiring IAIso into an OTEL-instrumented stack. Triggers on traces, spans, `execution_id` correlation, OTLP exporters. Do not use it for metrics — see `iaiso-deploy-prometheus-metrics`."
version: 1.0.0
tier: P1
category: deploy
framework: IAIso v5.0
license: See ../LICENSE
---

# IAIso traces on OpenTelemetry

## When this applies

Your app already uses OTEL. You want IAIso's step boundaries
visible alongside HTTP, DB, and LLM spans.

## Steps To Complete

1. **Configure the OTEL exporter** in IAIso. The reference
   SDK auto-detects standard `OTEL_*` env vars (endpoint,
   headers, service name) and emits to OTLP.

2. **Map IAIso identifiers to OTEL conventions.**

   - IAIso `execution_id` → OTEL `iaiso.execution_id`
     attribute, OR set as the trace ID if your scheme allows.
   - `engine.step` → span named `iaiso.step` with attributes
     `tokens`, `tool_calls`, `depth`, `pressure_post_step`.
   - `engine.escalation` → span event on the parent step
     span (not a separate span — it shares the boundary).
   - `engine.release` → span event with `pressure_pre_reset`.

3. **Propagate trace context across LLM-provider calls.** The
   middleware wrappers (`iaiso-llm-*`) honour W3C trace
   context if your provider SDK does. Do not start a new
   trace inside the wrapper — it breaks correlation.

4. **Sample sensibly.** A high-volume agent emits a step
   every few seconds. Apply head sampling at the
   BoundedExecution boundary, not per-step, so a sampled
   execution captures the whole trajectory or none of it.

5. **Correlate with audit events.** The audit envelope's
   `execution_id` and the trace's IAIso execution attribute
   are the same value — that is what makes
   audit-driven debugging fast.

## What this skill does NOT cover

- Metrics — see `../iaiso-deploy-prometheus-metrics/SKILL.md`.
- SIEM forwarding — see `iaiso-sink-*`.

## References

- `core/iaiso-python/iaiso/observability/tracing.py`
