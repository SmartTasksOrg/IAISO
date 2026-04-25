# Forwarding Audit Events to SIEM / Observability Platforms

IAIso ships three SIEM sinks: Splunk HEC, Datadog Logs, Elasticsearch.
Each produces events in the format the target platform documents. None
of them have been end-to-end tested against live vendor instances from
this codebase — the wire format is verified, the deployment-specific
behavior (index setup, parsing rules, retention) is not.

## Before deploying any SIEM sink

1. Confirm the endpoint URL for your region / deployment type.
2. Provision credentials (HEC token, API key, bulk user) with the
   minimum privileges needed.
3. Test with a small volume first. Watch the drops counter:
   `sink.dropped_events`.
4. Verify events land in the destination platform and are parsed
   correctly before routing production traffic.

## Splunk HEC

```python
from iaiso import BoundedExecution
from iaiso.audit.splunk import SplunkHECConfig, SplunkHECSink

sink = SplunkHECSink(SplunkHECConfig(
    url="https://splunk.example.com:8088/services/collector/event",
    token="your-hec-token-uuid",
    index="iaiso_audit",           # optional; uses token default otherwise
    sourcetype="iaiso:audit",      # configure field extraction in Splunk
))

with BoundedExecution.start(audit_sink=sink) as exec_:
    # ... agent work ...
    pass

sink.close()
```

Event format produced:

```json
{
  "time": 1700000000.123,
  "source": "iaiso",
  "sourcetype": "iaiso:audit",
  "index": "iaiso_audit",
  "event": {
    "kind": "engine.step",
    "execution_id": "exec-abc",
    "schema_version": "1.0",
    "pressure": 0.42,
    "tokens": 500
  }
}
```

Splunk-specific setup you'll want:
- Field extractions for the `iaiso:audit` sourcetype mapping JSON fields
  to indexed fields.
- Dashboards on `kind=engine.escalation` for alerting.
- Retention policy on the `iaiso_audit` index.

## Datadog Logs

```python
from iaiso.audit.datadog import DatadogLogsConfig, DatadogLogsSink

sink = DatadogLogsSink(DatadogLogsConfig(
    api_key="your-datadog-api-key",
    intake_url="https://http-intake.logs.datadoghq.eu/api/v2/logs",  # pick region
    service="iaiso",
    env="production",
    tags=["team:platform", "app:chat-agent"],
))
```

The sink sets Datadog's reserved attributes (`ddsource`, `service`,
`ddtags`, `timestamp`, `host`) and puts IAIso-specific fields under a
top-level `iaiso` key. In Datadog's log explorer, facet on
`@iaiso.kind` to filter by event type.

Regional endpoints: pick yours from
https://docs.datadoghq.com/api/latest/logs/

## Elasticsearch

```python
import base64
from iaiso.audit.elastic import ElasticConfig, ElasticSink

# Basic auth; for API key auth use "ApiKey <base64>" instead
creds = base64.b64encode(b"user:password").decode()
sink = ElasticSink(ElasticConfig(
    bulk_url="https://es.example.com:9200/_bulk",
    index="iaiso-audit-2026-04",
    auth_header=f"Basic {creds}",
))
```

The sink uses Elasticsearch's `_bulk` API with NDJSON. Each event
produces a document like:

```json
{
  "@timestamp": "2026-04-23T11:45:00.123Z",
  "kind": "engine.step",
  "execution_id": "exec-abc",
  "schema_version": "1.0",
  "iaiso": {
    "data": {
      "pressure": 0.42,
      "tokens": 500
    }
  }
}
```

For production:
- Set up an index template for `iaiso-audit-*` with appropriate
  mappings — `@timestamp` as date, `iaiso.data.pressure` as float,
  `kind` and `execution_id` as keyword.
- Use a data stream + ILM policy for rollover and retention.
- Consider a dedicated node role or tier for audit traffic.

## Fanning out to multiple destinations

```python
from iaiso import FanoutSink, JsonlFileSink

sink = FanoutSink(
    SplunkHECSink(splunk_cfg),           # ship to Splunk
    JsonlFileSink("/var/log/iaiso.jsonl"),  # also keep local archive
)
```

Failures in any one sink are logged to stderr; the others continue to
receive events.

## Operational notes

All SIEM sinks use a background thread and bounded queue. When the queue
is full (network is slow, destination is down), events are dropped
rather than blocking the agent. Monitor `sink.dropped_events` and
alert when it increases.

For higher-throughput deployments, consider running a local log
aggregator (fluent-bit, Vector, otelcol) and having IAIso ship to that
via the generic `WebhookSink` — the aggregator handles buffering,
retries, and protocol-specific formatting.
